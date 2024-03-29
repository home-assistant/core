"""The yolink integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from yolink.const import ATTR_DEVICE_SMART_REMOTER
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.home_manager import YoLinkHome
from yolink.message_listener import MessageListener

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import DOMAIN, YOLINK_EVENT
from .coordinator import YoLinkCoordinator
from .device_trigger import CONF_LONG_PRESS, CONF_SHORT_PRESS
from .services import async_register_services

SCAN_INTERVAL = timedelta(minutes=5)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
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
        device_coordinator = device_coordinators.get(device.device_id)
        if device_coordinator is None:
            return
        device_coordinator.async_set_updated_data(msg_data)
        # handling events
        if (
            device_coordinator.device.device_type == ATTR_DEVICE_SMART_REMOTER
            and msg_data.get("event") is not None
        ):
            device_registry = dr.async_get(self._hass)
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, device_coordinator.device.device_id)}
            )
            if device_entry is None:
                return
            key_press_type = None
            if msg_data["event"]["type"] == "Press":
                key_press_type = CONF_SHORT_PRESS
            else:
                key_press_type = CONF_LONG_PRESS
            button_idx = msg_data["event"]["keyMask"]
            event_data = {
                "type": f"button_{button_idx}_{key_press_type}",
                "device_id": device_entry.id,
            }
            self._hass.bus.async_fire(YOLINK_EVENT, event_data)


@dataclass
class YoLinkHomeStore:
    """YoLink home store."""

    home_instance: YoLinkHome
    device_coordinators: dict[str, YoLinkCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up YoLink."""

    async_register_services(hass)

    return True


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
        async with asyncio.timeout(10):
            await yolink_home.async_setup(
                auth_mgr, YoLinkHomeMessageListener(hass, entry)
            )
    except YoLinkAuthFailError as yl_auth_err:
        raise ConfigEntryAuthFailed from yl_auth_err
    except (YoLinkClientError, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    device_coordinators = {}

    # revese mapping
    device_pairing_mapping = {}
    for device in yolink_home.get_devices():
        if (parent_id := device.get_paired_device_id()) is not None:
            device_pairing_mapping[parent_id] = device.device_id

    for device in yolink_home.get_devices():
        paried_device: YoLinkDevice | None = None
        if (
            paried_device_id := device_pairing_mapping.get(device.device_id)
        ) is not None:
            paried_device = yolink_home.get_device(paried_device_id)
        device_coordinator = YoLinkCoordinator(hass, device, paried_device)
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
