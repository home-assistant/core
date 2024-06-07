"""Entity to track connections to websocket API."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DATA_CONNECTIONS,
    SIGNAL_WEBSOCKET_CONNECTED,
    SIGNAL_WEBSOCKET_DISCONNECTED,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the API streams platform."""
    entity = APICount()

    async_add_entities([entity])


class APICount(SensorEntity):
    """Entity to represent how many people are connected to the stream API."""

    _attr_name = "Connected clients"
    _attr_native_unit_of_measurement = "clients"

    def __init__(self) -> None:
        """Initialize the API count."""
        self._attr_native_value = 0

    async def async_added_to_hass(self) -> None:
        """Handle addition to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_WEBSOCKET_CONNECTED, self._update_count
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_WEBSOCKET_DISCONNECTED, self._update_count
            )
        )

    @callback
    def _update_count(self) -> None:
        self._attr_native_value = self.hass.data.get(DATA_CONNECTIONS, 0)
        self.async_write_ha_state()
