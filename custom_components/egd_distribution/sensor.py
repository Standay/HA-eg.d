"""Sensors for EG.D Distribution measurements."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VALID_STATUS
from .coordinator import EGDDistributionCoordinator

ENERGY_PROFILES = {"ICQ2", "ISQ2", "IKQ1", "IMQ2", "ICCS"}
POWER_PROFILES = {"ICC1", "ISC1", "IKC1", "IMC1"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up EG.D sensors."""
    coordinator: EGDDistributionCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([EGDLatestSensor(coordinator, entry), EGDSumSensor(coordinator, entry)])


class EGDBaseSensor(CoordinatorEntity[EGDDistributionCoordinator], SensorEntity):
    """Base class for EG.D sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"EG.D {coordinator.ean}",
            "manufacturer": "EG.D",
        }
        self._set_units()

    def _set_units(self) -> None:
        profile = self.coordinator.profile.upper()
        if profile in ENERGY_PROFILES:
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
        elif profile in POWER_PROFILES:
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_device_class = SensorDeviceClass.POWER


class EGDLatestSensor(EGDBaseSensor):
    """Latest valid EG.D measurement."""

    _attr_name = "Latest measurement"

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "latest")

    @property
    def native_value(self) -> float | None:
        for item in reversed(self.coordinator.data or []):
            if item.status in (None, VALID_STATUS):
                return item.value
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        for item in reversed(self.coordinator.data or []):
            if item.status in (None, VALID_STATUS):
                return {"timestamp": item.timestamp.isoformat(), "status": item.status or "unknown"}
        return None


class EGDSumSensor(EGDBaseSensor):
    """Energy calculated from valid values in the configured window."""

    _attr_name = "Window energy"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "window_energy")
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or []
        valid = [item.value for item in data if item.status in (None, VALID_STATUS)]
        if not valid:
            return None
        if self.coordinator.profile.upper() in POWER_PROFILES:
            return round(sum(valid) / 4, 6)
        return round(sum(valid), 6)

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        data = self.coordinator.data or []
        return {
            "days": self.coordinator.days,
            "profile": self.coordinator.profile,
            "calculation": "sum_kw_quarter_hours_divided_by_4" if self.coordinator.profile.upper() in POWER_PROFILES else "sum_values",
            "valid_samples": len([item for item in data if item.status in (None, VALID_STATUS)]),
            "total_samples": len(data),
        }
