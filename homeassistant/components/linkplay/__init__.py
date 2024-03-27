"""Support for LinkPlay devices."""

from datetime import timedelta

from linkplay.controller import LinkPlayController

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    BRIDGE_DISCOVERED,
    CONTROLLER,
    DISCOVERY_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry. Called when an entry has been setup."""

    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    controller = LinkPlayController(session)
    hass.data[DOMAIN][CONTROLLER] = controller
    bridge_uuids = []

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_scan_update(_=None):
        await controller.discover_bridges()
        await controller.discover_multirooms()

        for bridge in controller.bridges:
            if bridge.device.uuid in bridge_uuids:
                continue

            bridge_uuids.append(bridge.device.uuid)
            async_dispatcher_send(hass, BRIDGE_DISCOVERED, bridge)

    await _async_scan_update()

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
        )
    )

    return True
