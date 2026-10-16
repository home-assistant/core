"""Shared LoRaWAN connection registration and vendor discovery."""

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.service_info.lorawan import LoRaWANDiscoveryInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_lorawan

from . import websocket_api
from .connection import DATA_REGISTRY, ConnectionRegistry, async_register_connection
from .const import DOMAIN, SIGNAL_DEVICES_CHANGED
from .device_manager import DeviceManager, device_identifier
from .entity import LoRaWANEntity

__all__ = [
    "DeviceManager",
    "LoRaWANDiscoveryInfo",
    "LoRaWANEntity",
    "async_register_connection",
    "device_identifier",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LoRaWAN integration."""
    registry = hass.data[DATA_REGISTRY] = ConnectionRegistry(
        await async_get_lorawan(hass)
    )

    websocket_api.async_setup(hass)

    @callback
    def entry_changed(change: ConfigEntryChange, entry: ConfigEntry) -> None:
        if (
            entry.entry_id not in registry.devices
            and entry.domain not in registry.integrations
        ):
            return
        if change is ConfigEntryChange.REMOVED:
            registry.devices.pop(entry.entry_id, None)
        async_dispatcher_send(hass, SIGNAL_DEVICES_CHANGED)

    unsubscribe_entries = async_dispatcher_connect(
        hass, SIGNAL_CONFIG_ENTRY_CHANGED, entry_changed
    )

    @callback
    def shutdown(event: Event) -> None:
        for registered in tuple(registry.connections.values()):
            registered.unsubscribe()
        registry.connection_change_listeners.clear()
        registry.devices.clear()
        unsubscribe_entries()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
    return True
