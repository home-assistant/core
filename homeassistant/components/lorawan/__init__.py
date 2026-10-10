"""Shared LoRaWAN connection registration and vendor discovery."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_lorawan

from .connection import (
    DATA_REGISTRY,
    ConnectionRegistry,
    async_register_connection,
    async_subscribe_connections,
)
from .const import DOMAIN
from .device_manager import DeviceManager, device_identifier
from .entity import LoRaWANEntity

__all__ = [
    "DeviceManager",
    "LoRaWANEntity",
    "async_register_connection",
    "async_subscribe_connections",
    "device_identifier",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LoRaWAN integration."""
    registry = hass.data[DATA_REGISTRY] = ConnectionRegistry(
        await async_get_lorawan(hass)
    )

    @callback
    def shutdown(event: Event) -> None:
        for registered in tuple(registry.connections.values()):
            registered.unsubscribe()
        registry.changed.clear()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)
    return True
