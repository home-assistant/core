"""The yolink integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import async_timeout
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.home_manager import YoLinkHome
from yolink.message_listener import MessageListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import DOMAIN
from .coordinator import YoLinkCoordinator

SCAN_INTERVAL = timedelta(minutes=5)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]


class YoLinkHomeMessageListener(MessageListener):
    """YoLink home message listener."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init YoLink home message listener."""
        self._hass = hass
        self._entry = entry

    def on_message(self, device: YoLinkDevice, msg_data: dict[str, Any]) -> None:
        """On YoLink home message received."""
        entry_data = self._hass.data[DOMAIN].get(self._entry.entry_id)
        if not entry_data:
            return
        device_coordinators = entry_data.device_coordinators
        if not device_coordinators:
            return
        device_coordiantor = device_coordinators.get(device.device_id)
        if device_coordiantor is not None:
            device_coordiantor.async_set_updated_data(msg_data)


@dataclass
class YoLinkHomeStore:
    """YoLink home store."""

    home_instance: YoLinkHome
    device_coordinators: dict[str, YoLinkCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up yolink from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth_mgr = api.ConfigEntryAuth(
        hass, aiohttp_client.async_get_clientsession(hass), session
    )
    yolink_home = YoLinkHome()
    try:
        async with async_timeout.timeout(10):
            await yolink_home.async_setup(
                auth_mgr, YoLinkHomeMessageListener(hass, entry)
            )
    except YoLinkAuthFailError as yl_auth_err:
        raise ConfigEntryAuthFailed from yl_auth_err
    except (YoLinkClientError, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady from err

    device_coordinators = {}
    for device in yolink_home.get_devices():
        device_coordinator = YoLinkCoordinator(hass, device)
        try:
            await device_coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # Not failure by fetching device state
            device_coordinator.data = {}
        device_coordinators[device.device_id] = device_coordinator
    hass.data[DOMAIN][entry.entry_id] = YoLinkHomeStore(
        yolink_home, device_coordinators
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_yolink_unload(event) -> None:
        """Unload yolink."""
        await yolink_home.async_unload()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_yolink_unload)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id].home_instance.async_unload()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
