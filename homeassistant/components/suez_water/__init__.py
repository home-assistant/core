"""The Suez Water integration."""
from __future__ import annotations

from pysuez import SuezClient
from pysuez.client import PySuezError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_COUNTER_ID, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Suez Water from a config entry."""

    def get_client() -> SuezClient:
        try:
            client = SuezClient(
                entry.data[CONF_USERNAME],
                entry.data[CONF_PASSWORD],
                entry.data[CONF_COUNTER_ID],
                provider=None,
            )
            if not client.check_credentials():
                raise ConfigEntryError
            return client
        except PySuezError as ex:
            raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = await hass.async_add_executor_job(get_client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
