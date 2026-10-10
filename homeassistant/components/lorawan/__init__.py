"""Shared LoRaWAN connection registration and vendor discovery."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_lorawan

from .connection import (
    DATA_REGISTRY,
    ConnectionRegistry,
    async_get_connections as async_get_connections,
    async_register_connection as async_register_connection,
    async_subscribe_connections as async_subscribe_connections,
)
from .const import DOMAIN
from .device_manager import (
    DeviceManager as DeviceManager,
    device_identifier as device_identifier,
)
from .entity import LoRaWANEntity as LoRaWANEntity

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Load discovery matchers and release registrations when HA stops."""
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
