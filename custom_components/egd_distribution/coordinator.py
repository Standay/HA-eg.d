"""Data update coordinator for EG.D Distribution."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EGDDistributionApi, EGDDistributionApiError, EGDMeasurement
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .statistics import async_import_energy_statistics

_LOGGER = logging.getLogger(__name__)
_PRAGUE_TZ = ZoneInfo("Europe/Prague")
_PERIOD_AUTHORIZATION_MESSAGE = (
    "V po\u017eadovan\u00e9m obdob\u00ed nem\u00e1te opr\u00e1vn\u011bn\u00ed "
    "na data odb\u011brn\u00e9ho m\u00edsta"
)


class EGDDistributionCoordinator(DataUpdateCoordinator[list[EGDMeasurement]]):
    """Fetch and cache EG.D measurements."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EGDDistributionApi,
        ean: str,
        profile: str,
        data_source: str,
        days: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        self.ean = ean
        self.profile = profile
        self.data_source = data_source
        self.days = days
        self.last_error: str | None = None
        self.last_query_start: datetime | None = None
        self.last_query_end: datetime | None = None
        self.statistics_id: str | None = None
        self.last_statistics_imported = 0
        self.last_statistics_error: str | None = None

    async def _async_update_data(self) -> list[EGDMeasurement]:
        yesterday = datetime.now(_PRAGUE_TZ).date() - timedelta(days=1)
        end = datetime.combine(yesterday, time(23, 45), _PRAGUE_TZ).astimezone(UTC)
        start = datetime.combine(yesterday - timedelta(days=self.days - 1), time.min, _PRAGUE_TZ).astimezone(UTC)
        query_ranges = [(start, end)]
        if self.days > 1:
            query_ranges.append((datetime.combine(yesterday, time.min, _PRAGUE_TZ).astimezone(UTC), end))

        period_error: str | None = None
        for query_start, query_end in query_ranges:
            self.last_query_start = query_start
            self.last_query_end = query_end
            try:
                data = await self.api.async_get_measurements(
                    self.ean,
                    self.profile,
                    query_start,
                    query_end,
                    data_source=self.data_source,
                )
            except EGDDistributionApiError as err:
                if _is_period_authorization_error(err):
                    period_error = str(err)
                    _LOGGER.warning("EG.D rejected the requested data period: %s", err)
                    continue
                raise UpdateFailed(str(err)) from err
            self.last_error = None
            await self._async_import_statistics(data)
            return data

        if period_error is not None:
            self.last_error = period_error
            return self.data or []
        return []

    async def _async_import_statistics(self, data: list[EGDMeasurement]) -> None:
        """Import fetched interval data into Home Assistant long-term statistics."""
        try:
            (
                self.statistics_id,
                self.last_statistics_imported,
            ) = await async_import_energy_statistics(
                self.hass,
                self.ean,
                self.profile,
                self.data_source,
                data,
            )
        except Exception as err:  # noqa: BLE001
            self.last_statistics_error = str(err)
            self.last_statistics_imported = 0
            _LOGGER.warning("Could not import EG.D energy statistics: %s", err)
        else:
            self.last_statistics_error = None


def _is_period_authorization_error(err: EGDDistributionApiError) -> bool:
    """Return true for EG.D's validation error when the selected period is unavailable."""
    message = str(err)
    return (
        "HTTP 400" in message
        and "validation_error" in message
        and _PERIOD_AUTHORIZATION_MESSAGE in message
    )
