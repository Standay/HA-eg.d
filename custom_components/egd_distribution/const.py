"""Constants for the EG.D Distribution integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "egd_distribution"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_EAN = "ean"
CONF_PROFILE = "profile"
CONF_DAYS = "days"
CONF_TOKEN_URL = "token_url"
CONF_API_URL = "api_url"

DEFAULT_TOKEN_URL = "https://idm.distribuce24.cz/oauth/token"
DEFAULT_API_URL = "https://data.distribuce24.cz/rest"
DEFAULT_PROFILE = "ICQ2"
DEFAULT_DAYS = 7
DEFAULT_SCAN_INTERVAL = timedelta(hours=24)

OAUTH_SCOPE = "namerena_data_openapi"
VALID_STATUS = "IU012"
