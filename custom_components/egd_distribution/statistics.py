"""Long-term statistics import for EG.D interval measurements."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_add_external_statistics, statistics_during_period
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

    existing_rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        hourly_energy[0][0] - timedelta(hours=1),
        None,
        {statistic_id},
        "hour",
        None,
        {"state", "sum"},
    )
    statistics = _statistics_to_import(
        hourly_energy,
        existing_rows.get(statistic_id, []),
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


def _statistics_to_import(
    hourly_energy: list[tuple[datetime, float]],
    existing_rows: list[dict[str, Any]],
) -> list[StatisticData]:
    """Return hourly statistics with sums rebuilt for the whole import window."""
    first_start = hourly_energy[0][0]
    fetched_energy = dict(hourly_energy)
    combined_energy: dict[datetime, float] = {}
    baseline_sum = 0.0
    baseline_start: datetime | None = None

    for row in existing_rows:
        start = _row_start(row.get("start"))
        if start is None:
            continue
        row_sum = _row_float(row.get("sum"))
        if start < first_start:
            if row_sum is not None and (baseline_start is None or start > baseline_start):
                baseline_start = start
                baseline_sum = row_sum
            continue

        state = _row_float(row.get("state"))
        if state is not None:
            combined_energy[start] = state

    combined_energy.update(fetched_energy)

    running_sum = baseline_sum
    statistics: list[StatisticData] = []
    for start in sorted(combined_energy):
        if start < first_start:
            continue
        running_sum += combined_energy[start]
        statistics.append(
            StatisticData(
                start=start,
                state=round(combined_energy[start], 6),
                sum=round(running_sum, 6),
            )
        )
    return statistics


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


def _row_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None
