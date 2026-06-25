"""Async client for the EG.D/Distribuce24 OpenAPI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import OAUTH_SCOPE, default_data_source, is_c1_profile, normalize_profile


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
        data_source: str | None = None,
        page_size: int = 3000,
    ) -> list[EGDMeasurement]:
        """Fetch profile measurements, using the C1 or A/B endpoint as needed."""
        profile = normalize_profile(profile)
        if is_c1_profile(profile):
            return await self._async_get_c1_measurements(
                ean,
                profile,
                start,
                end,
                data_source or default_data_source(profile),
            )
        return await self._async_get_ab_measurements(ean, profile, start, end, page_size=page_size)

    async def _async_get_ab_measurements(
        self, ean: str, profile: str, start: datetime, end: datetime, *, page_size: int
    ) -> list[EGDMeasurement]:
        """Fetch A/B measurements from /spotreby, following PageStart/PageSize."""
        token = await self._async_get_token()
        measurements: list[EGDMeasurement] = []
        page_start = 0

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
                    "PageStart": str(page_start),
                    "PageSize": str(page_size),
                },
            )
            page_items = self._parse_ab_measurements(payload)
            measurements.extend(page_items)
            if len(page_items) < page_size:
                return measurements
            page_start += page_size

    async def _async_get_c1_measurements(
        self,
        ean: str,
        profile: str,
        start: datetime,
        end: datetime,
        data_source: str,
    ) -> list[EGDMeasurement]:
        """Fetch C1 measurements from /c/spotreby."""
        token = await self._async_get_token()
        payload = await self._async_request_json(
            "GET",
            f"{self._api_url}/c/spotreby",
            headers={"Authorization": f"Bearer {token}"},
            params=self._c1_params(ean, profile, start, end, data_source),
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
        """Parse documented C1 responses from /c/spotreby."""
        measurements: list[EGDMeasurement] = []
        for item in cls._iter_c1_measurement_rows(payload):
            timestamp = cls._first_str(item, "datetime", "timestamp", "dateTime")
            value = cls._first_number(item, "value")
            if timestamp is None or value is None:
                continue
            measurements.append(
                EGDMeasurement(
                    timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
                    value=value,
                    status=cls._first_str(item, "status"),
                )
            )
        return measurements

    @classmethod
    def _iter_c1_measurement_rows(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            groups = payload.get("MeasurementsValues")
            if isinstance(groups, list):
                rows: list[dict[str, Any]] = []
                for group in groups:
                    if not isinstance(group, dict):
                        continue
                    measurements = group.get("Measurements")
                    if isinstance(measurements, list):
                        rows.extend(item for item in measurements if isinstance(item, dict))
                return rows
        return cls._iter_payload_rows(payload)

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
    def _c1_params(ean: str, profile: str, start: datetime, end: datetime, data_source: str) -> dict[str, str]:
        return {
            "ean": ean,
            "profile": normalize_profile(profile),
            "from": EGDDistributionApi._format_datetime(start),
            "to": EGDDistributionApi._format_datetime(end),
            "zdrojDat": data_source,
        }
