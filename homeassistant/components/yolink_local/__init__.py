"""The YoLink Local integration."""

from __future__ import annotations

import asyncio

from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.local_hub_client import YoLinkLocalHubClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import CONF_NET_ID
from .coordinator import YoLinkLocalCoordinator
from .message_listener import LocalHubMessageListener

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


type YoLinkLocalConfigEntry = ConfigEntry[
    tuple[YoLinkLocalHubClient, dict[str, YoLinkLocalCoordinator]]
]


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

    device_pairing_mapping = {}
    for device in devices:
        if (parent_id := device.paired_device_id) is not None:
            device_pairing_mapping[parent_id] = device.device_id

    coordinators = {}

    for device in devices:
        paried_device: YoLinkDevice | None = None
        if (
            paried_device_id := device_pairing_mapping.get(device.device_id)
        ) is not None:
            paried_device = next(
                (
                    _device
                    for _device in devices
                    if _device.device_id == paried_device_id
                ),
                None,
            )
        coordinator = YoLinkLocalCoordinator(hass, entry, device, paried_device)
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # Not failure by fetching device state
            coordinator.data = {}
        coordinators[device.device_id] = coordinator

    entry.runtime_data = (client, coordinators)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        if entry.runtime_data is not None:
            client: YoLinkLocalHubClient = entry.runtime_data[0]
            await client.async_unload()
    return unload_ok
