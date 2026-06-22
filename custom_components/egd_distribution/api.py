"""Async client for the EG.D/Distribuce24 OpenAPI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import OAUTH_SCOPE


class EGDDistributionApiError(Exception):
    """Raised when the EG.D API request fails."""


@dataclass(frozen=True)
class EGDMeasurement:
    """Single EG.D profile measurement."""

    timestamp: datetime
    value: float
    status: str | None


class EGDDistributionApi:
    """Client for token and profile data endpoints documented by EG.D."""

    def __init__(
        self,
        session: ClientSession,
        client_id: str,
        client_secret: str,
        token_url: str,
        api_url: str,
    ) -> None:
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._api_url = api_url.rstrip("/")
        self._open_api_url = self._api_url.removesuffix("/rest") + "/openApi"
        self._access_token: str | None = None
        self._expires_at: datetime | None = None

    async def async_test_connection(self) -> None:
        """Validate OAuth credentials without requiring metering data to exist."""
        await self._async_get_token()

    async def async_get_measurements(
        self,
        ean: str,
        profile: str,
        start: datetime,
        end: datetime,
        *,
        page_size: int = 3000,
    ) -> list[EGDMeasurement]:
        """Fetch profile measurements, using the C1 or A/B endpoint as needed."""
        if self._is_c1_profile(profile):
            return await self._async_get_c1_measurements(ean, profile, start, end)
        return await self._async_get_ab_measurements(ean, profile, start, end, page_size=page_size)

    async def _async_get_ab_measurements(
        self, ean: str, profile: str, start: datetime, end: datetime, *, page_size: int
    ) -> list[EGDMeasurement]:
        """Fetch A/B measurements from /rest/spotreby, following pageStart/pageSize."""
        token = await self._async_get_token()
        measurements: list[EGDMeasurement] = []
        page_start = 1

        while True:
            payload = await self._async_request_json(
                "GET",
                f"{self._api_url}/spotreby",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "ean": ean,
                    "profile": profile,
                    "from": self._format_datetime(start),
                    "to": self._format_datetime(end),
                    "pageStart": str(page_start),
                    "pageSize": str(page_size),
                },
            )
            page_items = self._parse_ab_measurements(payload)
            measurements.extend(page_items)
            if len(page_items) < page_size:
                return measurements
            page_start += len(page_items)

    async def _async_get_c1_measurements(self, ean: str, profile: str, start: datetime, end: datetime) -> list[EGDMeasurement]:
        """Fetch C1 smart-meter measurements from /openApi/spotreby."""
        token = await self._async_get_token()
        payload = await self._async_request_json(
            "GET",
            f"{self._open_api_url}/spotreby",
            headers={"Authorization": f"Bearer {token}"},
            params=self._c1_params(ean, profile, start, end),
        )
        return self._parse_c1_measurements(payload)

    async def _async_get_token(self) -> str:
        now = datetime.now(UTC)
        if self._access_token and self._expires_at and self._expires_at > now + timedelta(minutes=5):
            return self._access_token

        payload = await self._async_request_json(
            "POST",
            self._token_url,
            json={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": OAUTH_SCOPE,
            },
        )
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise EGDDistributionApiError("Token response did not contain access_token")

        expires = payload.get("expires") if isinstance(payload, dict) else None
        expires_seconds = int(expires) / 1000 if isinstance(expires, int | float) else 3600
        self._access_token = token
        self._expires_at = now + timedelta(seconds=expires_seconds)
        return token

    async def _async_request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        try:
            async with self._session.request(method, url, **kwargs) as response:
                if response.status >= 400:
                    message = await response.text()
                    raise EGDDistributionApiError(f"EG.D API returned HTTP {response.status}: {message}")
                try:
                    return await response.json()
                except Exception as err:
                    message = await response.text()
                    raise EGDDistributionApiError(f"EG.D API returned invalid JSON: {message}") from err
        except TimeoutError as err:
            raise EGDDistributionApiError("Timeout while communicating with EG.D API") from err
        except ClientError as err:
            raise EGDDistributionApiError(f"Communication with EG.D API failed: {err}") from err

    @staticmethod
    def _parse_ab_measurements(payload: Any) -> list[EGDMeasurement]:
        measurements: list[EGDMeasurement] = []
        groups = payload if isinstance(payload, list) else [payload]
        for group in groups:
            if not isinstance(group, dict):
                continue
            for item in group.get("data", []):
                if not isinstance(item, dict):
                    continue
                timestamp = item.get("timestamp")
                value = item.get("value")
                if not isinstance(timestamp, str) or not isinstance(value, int | float):
                    continue
                measurements.append(
                    EGDMeasurement(
                        timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
                        value=float(value),
                        status=item.get("status") if isinstance(item.get("status"), str) else None,
                    )
                )
        return measurements

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @classmethod
    def _parse_c1_measurements(cls, payload: Any) -> list[EGDMeasurement]:
        """Parse C1 responses from /openApi/spotreby.

        EG.D documents C1 under the separate /openApi path and without a profile
        parameter. The response shape differs from the A/B profile wrapper, so this
        parser accepts common Czech/English field names used for consumption rows.
        """
        measurements: list[EGDMeasurement] = []
        for item in cls._iter_payload_rows(payload):
            timestamp = cls._first_str(item, "timestamp", "dateTime", "datetime", "datum", "cas", "čas", "from", "od", "to", "do")
            value = cls._first_number(item, "spotreba", "consumption", "value", "hodnota", "mnozstvi", "množství")
            if timestamp is None or value is None:
                continue
            measurements.append(
                EGDMeasurement(
                    timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
                    value=float(value),
                    status=cls._first_str(item, "statusSpotreba", "consumptionStatus", "status", "stav"),
                )
            )
        return measurements

    @staticmethod
    def _iter_payload_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("data", "items", "values", "spotreby", "measurements"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        return [payload]

    @staticmethod
    def _first_str(item: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _first_number(item: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = item.get(key)
            if isinstance(value, int | float):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value.replace(",", "."))
                except ValueError:
                    continue
        return None

    @staticmethod
    def _c1_params(ean: str, profile: str, start: datetime, end: datetime) -> dict[str, str]:
        params = {
            "ean": ean,
            "from": EGDDistributionApi._format_datetime(start),
            "to": EGDDistributionApi._format_datetime(end),
        }
        if profile.upper() not in {"C1", "C"}:
            params["profile"] = profile
        return params

    @staticmethod
    def _is_c1_profile(profile: str) -> bool:
        return profile.upper() in {"C1", "C"} or profile.startswith("0.0.")
