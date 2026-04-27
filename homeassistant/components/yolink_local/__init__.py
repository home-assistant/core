"""The YoLink Local integration."""

from __future__ import annotations

import asyncio

from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.local_hub_client import YoLinkLocalHubClient

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import CONF_NET_ID
from .coordinator import YoLinkLocalCoordinator
from .message_listener import LocalHubMessageListener
from .model import YoLinkLocalConfigEntry, YoLinkLocalData

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: YoLinkLocalConfigEntry) -> bool:
    """Set up YoLink Local from a config entry."""

    session = aiohttp_client.async_create_clientsession(hass)

    client = YoLinkLocalHubClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_NET_ID],
        entry.data[CONF_CLIENT_ID],
        entry.data[CONF_CLIENT_SECRET],
    )
    try:
        async with asyncio.timeout(10):
            await client.async_setup(LocalHubMessageListener(hass, entry))
    except YoLinkAuthFailError as yl_auth_err:
        raise ConfigEntryAuthFailed from yl_auth_err
    except (YoLinkClientError, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    devices: list[YoLinkDevice] = client.get_devices()

    coordinators = {}

    for device in devices:
        coordinator = YoLinkLocalCoordinator(hass, entry, device)
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # Not failure by fetching device state
            coordinator.data = {}
        coordinators[device.device_id] = coordinator

    entry.runtime_data = YoLinkLocalData(client, coordinators)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: YoLinkLocalConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        if (runtime_data := entry.runtime_data) is not None:
            await runtime_data.client.async_unload()
    return unload_ok
