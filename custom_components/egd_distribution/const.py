"""Constants for the EG.D Distribution integration."""

from __future__ import annotations

from datetime import timedelta
import re

DOMAIN = "egd_distribution"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_EAN = "ean"
CONF_PROFILE = "profile"
CONF_DATA_SOURCE = "zdroj_dat"
CONF_DAYS = "days"
CONF_TOKEN_URL = "token_url"
CONF_API_URL = "api_url"

DEFAULT_TOKEN_URL = "https://idm.distribuce24.cz/oauth/token"
DEFAULT_API_URL = "https://data.distribuce24.cz/rest"
DEFAULT_PROFILE = "DCQC"
DATA_SOURCE_SITE = "ODBERNE_MISTO"
DATA_SOURCE_METER = "ELEKTROMER"
DATA_SOURCES = [DATA_SOURCE_SITE, DATA_SOURCE_METER]
DEFAULT_DAYS = 7
DEFAULT_SCAN_INTERVAL = timedelta(hours=24)

OAUTH_SCOPE = "namerena_data_openapi"
AB_VALID_STATUS = "IU012"
C1_VALID_STATUS = "W"
VALID_STATUSES = {AB_VALID_STATUS, C1_VALID_STATUS}

ENERGY_PROFILES = {
    "C1",
    "DCQC",
    "DCQD",
    "DCQS",
    "DSQC",
    "DSQS",
    "ICQ2",
    "ISQ2",
    "IKQ1",
    "IMQ2",
    "ICCS",
}
POWER_PROFILES = {"ICC1", "ISC1", "IKC1", "IMC1"}

C1_SITE_PROFILE_CODES = {
    "0.0.2.4.1.2.12.0.0.0.0.0.0.0.0.3.72.0",
    "0.0.2.4.19.2.12.0.0.0.0.0.0.0.0.3.72.0",
}


def normalize_profile(profile: str) -> str:
    """Return the profile code that should be sent to EG.D."""
    cleaned = profile.strip()
    if cleaned.upper() in {"C", "C1"}:
        return DEFAULT_PROFILE
    return cleaned.upper()


def is_c1_profile(profile: str) -> bool:
    """Return true for C1 profile codes from the EG.D code list."""
    normalized = normalize_profile(profile)
    return normalized.startswith("0.0.")


def is_energy_profile(profile: str) -> bool:
    """Return true when profile values are interval energy in kWh."""
    normalized = normalize_profile(profile)
    return normalized in ENERGY_PROFILES or is_c1_profile(normalized)


def is_power_profile(profile: str) -> bool:
    """Return true when profile values are interval average power in kW."""
    return normalize_profile(profile) in POWER_PROFILES


def measurement_value_to_kwh(profile: str, value: float) -> float:
    """Convert an EG.D interval value to kWh."""
    if is_power_profile(profile):
        return value / 4
    return value


def statistic_id_for_profile(ean: str, profile: str, data_source: str | None = None) -> str:
    """Return a stable external statistic id for this EAN/profile pair."""
    parts = [ean, normalize_profile(profile)]
    if is_c1_profile(profile) and data_source:
        parts.append(data_source)
    slug = re.sub(r"[^a-z0-9_]+", "_", "_".join(parts).lower()).strip("_")
    return f"{DOMAIN}:{slug}_energy"


def default_data_source(profile: str) -> str:
    """Return the documented C1 zdrojDat default for a profile code."""
    normalized = normalize_profile(profile)
    if normalized in C1_SITE_PROFILE_CODES:
        return DATA_SOURCE_SITE
    return DATA_SOURCE_METER
