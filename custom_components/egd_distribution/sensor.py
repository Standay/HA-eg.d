"""Sensors for EG.D Distribution measurements."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EGDMeasurement
from .const import (
    DOMAIN,
    VALID_STATUSES,
    is_energy_profile,
    is_power_profile,
    measurement_value_to_kwh,
)
from .coordinator import EGDDistributionCoordinator

_PRAGUE_TZ = ZoneInfo("Europe/Prague")


def _is_valid_measurement_status(status: str | None) -> bool:
    return status in VALID_STATUSES


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up EG.D sensors."""
    coordinator: EGDDistributionCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            EGDLatestSensor(coordinator, entry),
            EGDWindowEnergySensor(coordinator, entry),
            EGDYesterdayEnergySensor(coordinator, entry),
            EGDLastDataTimestampSensor(coordinator, entry),
            EGDDataCoverageSensor(coordinator, entry),
        ]
    )


class EGDBaseSensor(CoordinatorEntity[EGDDistributionCoordinator], SensorEntity):
    """Base class for EG.D sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.ean)},
            "name": f"EG.D {coordinator.ean}",
            "manufacturer": "EG.D",
        }
        self._set_units()

    def _set_units(self) -> None:
        profile = self.coordinator.profile
        if is_energy_profile(profile):
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
        elif is_power_profile(profile):
            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
            self._attr_device_class = SensorDeviceClass.POWER

    def _base_extra_state_attributes(self) -> dict[str, int | str]:
        attrs: dict[str, int | str] = {
            "days": self.coordinator.days,
            "profile": self.coordinator.profile,
            "data_source": self.coordinator.data_source,
        }
        if self.coordinator.last_query_start is not None:
            attrs["last_query_start"] = self.coordinator.last_query_start.isoformat()
        if self.coordinator.last_query_end is not None:
            attrs["last_query_end"] = self.coordinator.last_query_end.isoformat()
        if self.coordinator.last_error is not None:
            attrs["last_error"] = self.coordinator.last_error
        if self.coordinator.statistics_id is not None:
            attrs["statistics_id"] = self.coordinator.statistics_id
            attrs["last_statistics_imported"] = self.coordinator.last_statistics_imported
        if self.coordinator.last_statistics_error is not None:
            attrs["last_statistics_error"] = self.coordinator.last_statistics_error
        return attrs


class EGDLatestSensor(EGDBaseSensor):
    """Latest valid EG.D measurement."""

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "latest")
        self._attr_name = (
            "Latest interval average power"
            if is_power_profile(coordinator.profile)
            else "Latest interval energy"
        )

    @property
    def native_value(self) -> float | None:
        for item in reversed(self.coordinator.data or []):
            if _is_valid_measurement_status(item.status):
                return item.value
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | str] | None:
        attrs = self._base_extra_state_attributes()
        for item in reversed(self.coordinator.data or []):
            if _is_valid_measurement_status(item.status):
                attrs.update({"timestamp": item.timestamp.isoformat(), "status": item.status or "unknown"})
                return attrs
        return attrs


class EGDWindowEnergySensor(EGDBaseSensor):
    """Energy calculated from valid values in the configured fetch window."""

    _attr_name = "Fetched period energy"

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "window_energy")
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY

    @property
    def native_value(self) -> float | None:
        valid = _valid_measurements(self.coordinator.data or [])
        if not valid:
            return None
        return round(
            sum(measurement_value_to_kwh(self.coordinator.profile, item.value) for item in valid),
            6,
        )

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        data = self.coordinator.data or []
        valid = _valid_measurements(data)
        attrs = self._base_extra_state_attributes()
        attrs.update(
            {
                "calculation": (
                    "sum_kw_quarter_hours_divided_by_4"
                    if is_power_profile(self.coordinator.profile)
                    else "sum_values"
                ),
                "valid_samples": len(valid),
                "total_samples": len(data),
            }
        )
        return attrs


class EGDYesterdayEnergySensor(EGDBaseSensor):
    """Energy calculated for the newest complete local day returned by EG.D."""

    _attr_name = "Yesterday energy"

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "yesterday_energy")
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY

    @property
    def native_value(self) -> float | None:
        target = _latest_local_date(self.coordinator)
        if target is None:
            return None
        valid = [
            item
            for item in _valid_measurements(self.coordinator.data or [])
            if _local_date(item) == target
        ]
        if not valid:
            return None
        return round(
            sum(measurement_value_to_kwh(self.coordinator.profile, item.value) for item in valid),
            6,
        )

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        target = _latest_local_date(self.coordinator)
        data = self.coordinator.data or []
        valid = [
            item
            for item in _valid_measurements(data)
            if target is not None and _local_date(item) == target
        ]
        total = [item for item in data if target is not None and _local_date(item) == target]
        attrs = self._base_extra_state_attributes()
        if target is not None:
            attrs["date"] = target.isoformat()
            attrs["expected_samples"] = _expected_samples_for_local_date(target)
        attrs.update({"valid_samples": len(valid), "total_samples": len(total)})
        return attrs


class EGDLastDataTimestampSensor(EGDBaseSensor):
    """Timestamp of the latest valid EG.D interval."""

    _attr_name = "Last data timestamp"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "last_data_timestamp")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_native_unit_of_measurement = None

    @property
    def native_value(self) -> datetime | None:
        item = _latest_valid_measurement(self.coordinator.data or [])
        return item.timestamp if item is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, int | str] | None:
        attrs = self._base_extra_state_attributes()
        item = _latest_valid_measurement(self.coordinator.data or [])
        if item is not None:
            attrs["status"] = item.status or "unknown"
        return attrs


class EGDDataCoverageSensor(EGDBaseSensor):
    """Share of expected samples returned as valid values."""

    _attr_name = "Data coverage"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: EGDDistributionCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "data_coverage")
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = None

    @property
    def native_value(self) -> float | None:
        expected = _expected_samples_for_query(self.coordinator)
        if expected <= 0:
            return None
        valid = len(_valid_measurements(self.coordinator.data or []))
        return round(valid / expected * 100, 1)

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        expected = _expected_samples_for_query(self.coordinator)
        data = self.coordinator.data or []
        attrs = self._base_extra_state_attributes()
        attrs.update(
            {
                "expected_samples": expected,
                "valid_samples": len(_valid_measurements(data)),
                "total_samples": len(data),
            }
        )
        return attrs


def _valid_measurements(data: list[EGDMeasurement]) -> list[EGDMeasurement]:
    return [item for item in data if _is_valid_measurement_status(item.status)]


def _latest_valid_measurement(data: list[EGDMeasurement]) -> EGDMeasurement | None:
    for item in reversed(data):
        if _is_valid_measurement_status(item.status):
            return item
    return None


def _local_date(item: EGDMeasurement) -> date:
    return item.timestamp.astimezone(_PRAGUE_TZ).date()


def _latest_local_date(coordinator: EGDDistributionCoordinator) -> date | None:
    if coordinator.last_query_end is None:
        return None
    return coordinator.last_query_end.astimezone(_PRAGUE_TZ).date()


def _expected_samples_for_query(coordinator: EGDDistributionCoordinator) -> int:
    if coordinator.last_query_start is None or coordinator.last_query_end is None:
        return 0
    seconds = (coordinator.last_query_end - coordinator.last_query_start).total_seconds()
    return max(0, int(seconds // 900) + 1)


def _expected_samples_for_local_date(value: date) -> int:
    start = datetime.combine(value, time.min, _PRAGUE_TZ).astimezone(UTC)
    end = datetime.combine(value + timedelta(days=1), time.min, _PRAGUE_TZ).astimezone(UTC)
    return int((end - start).total_seconds() // 900)
