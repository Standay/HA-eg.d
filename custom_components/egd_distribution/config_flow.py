"""Config flow for EG.D Distribution."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from aiohttp import ClientSession

from homeassistant import config_entries

from .api import EGDDistributionApi, EGDDistributionApiError
from .const import (
    CONF_API_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DATA_SOURCE,
    CONF_DAYS,
    CONF_EAN,
    CONF_PROFILE,
    CONF_TOKEN_URL,
    DATA_SOURCES,
    DEFAULT_API_URL,
    DEFAULT_DAYS,
    DEFAULT_PROFILE,
    DEFAULT_TOKEN_URL,
    DOMAIN,
    default_data_source,
    is_c1_profile,
    normalize_profile,
)


def _runtime_options_from_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return normalized runtime options from a submitted form."""
    profile = normalize_profile(user_input[CONF_PROFILE])
    return {
        CONF_PROFILE: profile,
        CONF_DATA_SOURCE: user_input.get(CONF_DATA_SOURCE) or default_data_source(profile),
        CONF_DAYS: user_input[CONF_DAYS],
        CONF_TOKEN_URL: user_input[CONF_TOKEN_URL].strip(),
        CONF_API_URL: user_input[CONF_API_URL].strip().rstrip("/"),
    }


def _runtime_schema_items(defaults: dict[str, Any]) -> dict[Any, Any]:
    """Return the shared setup/options schema items for runtime settings."""
    profile = normalize_profile(defaults.get(CONF_PROFILE, DEFAULT_PROFILE))
    return {
        vol.Required(CONF_PROFILE, default=profile): str,
        vol.Required(
            CONF_DATA_SOURCE,
            default=defaults.get(CONF_DATA_SOURCE, default_data_source(profile)),
        ): vol.In(DATA_SOURCES),
        vol.Required(
            CONF_DAYS,
            default=defaults.get(CONF_DAYS, DEFAULT_DAYS),
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
        vol.Required(
            CONF_TOKEN_URL,
            default=defaults.get(CONF_TOKEN_URL, DEFAULT_TOKEN_URL),
        ): str,
        vol.Required(
            CONF_API_URL,
            default=defaults.get(CONF_API_URL, DEFAULT_API_URL),
        ): str,
    }


def _runtime_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the shared setup/options schema for runtime settings."""
    return vol.Schema(_runtime_schema_items(defaults))


class EGDDistributionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an EG.D Distribution config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_CLIENT_ID] = user_input[CONF_CLIENT_ID].strip()
            user_input[CONF_CLIENT_SECRET] = user_input[CONF_CLIENT_SECRET].strip()
            user_input[CONF_EAN] = user_input[CONF_EAN].strip()
            user_input.update(_runtime_options_from_input(user_input))
            unique_id = f"{user_input[CONF_EAN]}_{user_input[CONF_PROFILE]}"
            if is_c1_profile(user_input[CONF_PROFILE]):
                unique_id = f"{unique_id}_{user_input[CONF_DATA_SOURCE]}"
            await self.async_set_unique_id(unique_id)
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
                title = f"EG.D {user_input[CONF_EAN]} {user_input[CONF_PROFILE]}"
                if is_c1_profile(user_input[CONF_PROFILE]):
                    title = f"{title} {user_input[CONF_DATA_SOURCE]}"
                return self.async_create_entry(
                    title=title,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_EAN): str,
                    **_runtime_schema_items({}),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return EGDDistributionOptionsFlow(config_entry)


class EGDDistributionOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    """Handle EG.D runtime options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage EG.D options."""
        errors: dict[str, str] = {}
        defaults = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            options = _runtime_options_from_input(user_input)
            try:
                async with ClientSession() as session:
                    api = EGDDistributionApi(
                        session,
                        self.config_entry.data[CONF_CLIENT_ID],
                        self.config_entry.data[CONF_CLIENT_SECRET],
                        options[CONF_TOKEN_URL],
                        options[CONF_API_URL],
                    )
                    await api.async_test_connection()
            except EGDDistributionApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=_runtime_schema(defaults),
            errors=errors,
        )
