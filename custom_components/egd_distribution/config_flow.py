"""Config flow for EG.D Distribution."""

from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientSession

from homeassistant import config_entries

from .api import EGDDistributionApi, EGDDistributionApiError
from .const import CONF_API_URL, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_DAYS, CONF_EAN, CONF_PROFILE, CONF_TOKEN_URL, DEFAULT_API_URL, DEFAULT_DAYS, DEFAULT_PROFILE, DEFAULT_TOKEN_URL, DOMAIN


class EGDDistributionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an EG.D Distribution config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_EAN]}_{user_input[CONF_PROFILE]}")
            self._abort_if_unique_id_configured()
            try:
                async with ClientSession() as session:
                    api = EGDDistributionApi(
                        session,
                        user_input[CONF_CLIENT_ID],
                        user_input[CONF_CLIENT_SECRET],
                        user_input[CONF_TOKEN_URL],
                        user_input[CONF_API_URL],
                    )
                    await api.async_test_connection()
            except EGDDistributionApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"EG.D {user_input[CONF_EAN]} {user_input[CONF_PROFILE]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_EAN): str,
                    vol.Required(CONF_PROFILE, default=DEFAULT_PROFILE): str,
                    vol.Required(CONF_DAYS, default=DEFAULT_DAYS): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
                    vol.Required(CONF_TOKEN_URL, default=DEFAULT_TOKEN_URL): str,
                    vol.Required(CONF_API_URL, default=DEFAULT_API_URL): str,
                }
            ),
            errors=errors,
        )
