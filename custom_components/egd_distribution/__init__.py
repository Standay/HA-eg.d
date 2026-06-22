"""EG.D Distribution integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EGDDistributionApi
from .const import CONF_API_URL, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_DAYS, CONF_EAN, CONF_PROFILE, CONF_TOKEN_URL, DOMAIN
from .coordinator import EGDDistributionCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EG.D Distribution from a config entry."""
    session = async_get_clientsession(hass)
    api = EGDDistributionApi(
        session,
        entry.data[CONF_CLIENT_ID],
        entry.data[CONF_CLIENT_SECRET],
        entry.data[CONF_TOKEN_URL],
        entry.data[CONF_API_URL],
    )
    coordinator = EGDDistributionCoordinator(
        hass,
        api,
        entry.data[CONF_EAN],
        entry.data[CONF_PROFILE],
        entry.data[CONF_DAYS],
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EG.D Distribution."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
