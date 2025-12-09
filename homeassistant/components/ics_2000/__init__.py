"""The KlikAanKlikUit ICS-2000 integration."""

from __future__ import annotations

from ics_2000.exceptions import InvalidAuthException
from ics_2000.hub import Hub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError

from .const import CONF_HOME_ID

_PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH]

type HubConfigEntry = ConfigEntry[Hub]


async def async_setup_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Set up KlikAanKlikUit ICS-2000 from a config entry."""
    hub = Hub(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    hub.local_address = entry.data.get(CONF_IP_ADDRESS)
    try:
        await hass.async_add_executor_job(hub.login)
    except InvalidAuthException as exs:
        raise ConfigEntryAuthFailed from exs
    home_id = entry.data.get(CONF_HOME_ID)
    if home_id is not None:
        await hass.async_add_executor_job(hub.select_home, home_id)
    else:
        raise ConfigEntryError
    await hass.async_add_executor_job(hub.get_devices)
    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
