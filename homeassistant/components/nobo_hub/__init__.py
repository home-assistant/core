"""The Nobø Ecohub integration."""

from __future__ import annotations

from pynobo import nobo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import CONF_AUTO_DISCOVERED, CONF_SERIAL

PLATFORMS = [Platform.CLIMATE, Platform.SELECT, Platform.SENSOR]

type NoboHubConfigEntry = ConfigEntry[nobo]


async def async_setup_entry(hass: HomeAssistant, entry: NoboHubConfigEntry) -> bool:
    """Set up Nobø Ecohub from a config entry."""

    serial = entry.data[CONF_SERIAL]
    discover = entry.data[CONF_AUTO_DISCOVERED]
    ip_address = None if discover else entry.data[CONF_IP_ADDRESS]
    hub = nobo(
        serial=serial,
        ip=ip_address,
        discover=discover,
        synchronous=False,
        timezone=dt_util.get_default_time_zone(),
    )
    await hub.connect()

    async def _async_close(event):
        """Close the Nobø Ecohub socket connection when HA stops."""
        await hub.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
    )
    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await hub.start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NoboHubConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.stop()

    return unload_ok
