"""Data update coordinator for EG.D Distribution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EGDDistributionApi, EGDDistributionApiError, EGDMeasurement
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EGDDistributionCoordinator(DataUpdateCoordinator[list[EGDMeasurement]]):
    """Fetch and cache EG.D measurements."""

    def __init__(self, hass: HomeAssistant, api: EGDDistributionApi, ean: str, profile: str, days: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        self.ean = ean
        self.profile = profile
        self.days = days

    async def _async_update_data(self) -> list[EGDMeasurement]:
        try:
            end = datetime.now(UTC)
            start = end - timedelta(days=self.days)
            return await self.api.async_get_measurements(self.ean, self.profile, start, end)
        except EGDDistributionApiError as err:
            raise UpdateFailed(str(err)) from err
