"""Base class for Airtouch5 entities."""

from airtouch5py.airtouch5_client import Airtouch5ConnectionStateChange
from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class Airtouch5Entity(Entity):
    """Base class for Airtouch5 entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = DOMAIN

    def __init__(self, client: Airtouch5SimpleClient) -> None:
        """Initialise the Entity."""
        self._client = client
        self._attr_available = True

    @callback
    def _receive_connection_callback(
        self, state: Airtouch5ConnectionStateChange
    ) -> None:
        self._attr_available = state is Airtouch5ConnectionStateChange.CONNECTED
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        self._client.connection_state_callbacks.append(
            self._receive_connection_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener when entity is removed from homeassistant."""
        self._client.connection_state_callbacks.remove(
            self._receive_connection_callback
        )
