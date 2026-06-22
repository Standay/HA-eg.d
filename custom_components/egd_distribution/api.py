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
        self._access_token: str | None = None
        self._expires_at: datetime | None = None

    async def async_test_connection(self) -> None:
        """Validate credentials without requiring recent metering data to exist.

        EG.D updates measurements daily and some valid EAN/profile combinations may
        legitimately return no recent samples. The config flow therefore verifies
        only that OAuth credentials work and that the data API accepts the token.
        """
        token = await self._async_get_token()
        await self._async_request_json(
            "GET",
            f"{self._api_url}/statusy",
            headers={"Authorization": f"Bearer {token}"},
        )

    async def async_get_measurements(
        self,
        ean: str,
        profile: str,
        start: datetime,
        end: datetime,
        *,
        page_size: int = 3000,
    ) -> list[EGDMeasurement]:
        """Fetch profile measurements from /spotreby, following pageStart/pageSize."""
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
            page_items = self._parse_measurements(payload)
            measurements.extend(page_items)
            if len(page_items) < page_size:
                return measurements
            page_start += len(page_items)

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
    def _parse_measurements(payload: Any) -> list[EGDMeasurement]:
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
