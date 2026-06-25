"""Long-term statistics import for EG.D interval measurements."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics, get_last_statistics
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant

from .api import EGDMeasurement
from .const import (
    DOMAIN,
    VALID_STATUSES,
    is_energy_profile,
    is_power_profile,
    measurement_value_to_kwh,
    statistic_id_for_profile,
)


def supports_energy_statistics(profile: str) -> bool:
    """Return true when the profile can be represented as energy statistics."""
    return is_energy_profile(profile) or is_power_profile(profile)


async def async_import_energy_statistics(
    hass: HomeAssistant,
    ean: str,
    profile: str,
    data_source: str,
    measurements: list[EGDMeasurement],
) -> tuple[str | None, int]:
    """Import valid 15-minute EG.D values as hourly external energy statistics."""
    if not supports_energy_statistics(profile):
        return None, 0

    hourly_energy = _hourly_energy(measurements, profile)
    statistic_id = statistic_id_for_profile(ean, profile, data_source)
    if not hourly_energy:
        return statistic_id, 0

    last_sum = 0.0
    last_start: datetime | None = None
    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics,
        hass,
        1,
        statistic_id,
        False,
        {"sum"},
    )
    if statistic_id in last_stats:
        row = last_stats[statistic_id][0]
        last_sum = float(row.get("sum") or 0)
        last_start = _row_start(row.get("start"))

    statistics: list[StatisticData] = []
    running_sum = last_sum
    for start, energy in hourly_energy:
        if last_start is not None and start <= last_start:
            continue
        running_sum += energy
        statistics.append(
            StatisticData(
                start=start,
                state=round(energy, 6),
                sum=round(running_sum, 6),
            )
        )

    if not statistics:
        return statistic_id, 0

    async_add_external_statistics(
        hass,
        StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=f"EG.D {ean} {profile} energy",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        statistics,
    )
    return statistic_id, len(statistics)


def _hourly_energy(measurements: list[EGDMeasurement], profile: str) -> list[tuple[datetime, float]]:
    hourly: defaultdict[datetime, float] = defaultdict(float)
    for item in measurements:
        if item.status not in VALID_STATUSES:
            continue
        start = item.timestamp.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        hourly[start] += measurement_value_to_kwh(profile, item.value)
    return sorted(hourly.items())


def _row_start(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    return None
