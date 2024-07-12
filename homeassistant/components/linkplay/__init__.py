"""Support for LinkPlay devices."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from linkplay.controller import LinkPlayController

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import BRIDGE_DISCOVERED, DISCOVERY_SCAN_INTERVAL, PLATFORMS


@dataclass
class LinkPlayData:
    """Data for LinkPlay."""

    controller: LinkPlayController


type LinkPlayConfigEntry = ConfigEntry[LinkPlayData]


async def async_setup_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Async setup hass config entry. Called when an entry has been setup."""

    session = async_get_clientsession(hass)
    controller = LinkPlayController(session)
    entry.runtime_data = LinkPlayData(controller=controller)

    bridge_uuids = []

    async def _async_scan_update(now: datetime | None) -> None:
        await controller.discover_bridges()
        await controller.discover_multirooms()

        for bridge in controller.bridges:
            if bridge.device.uuid in bridge_uuids:
                continue

            bridge_uuids.append(bridge.device.uuid)
            async_dispatcher_send(hass, BRIDGE_DISCOVERED, bridge)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.async_create_task(_async_scan_update(None), eager_start=True)

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LinkPlayConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
