"""Base class for Airtouch5 entities."""

import logging

from airtouch5py.airtouch5_client import Airtouch5ConnectionStateChange
from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class Airtouch5Entity(Entity):
    """Base class for Airtouch5 entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, client: Airtouch5SimpleClient) -> None:
        """Initialise the Entity."""
        self._client = client
        self._attr_available = True

    @callback
    def _receive_connection_callback(
        self, state: Airtouch5ConnectionStateChange
    ) -> None:
        _LOGGER.debug(
            "Connection state changed for %s (unique_id=%s): %s",
            self.entity_id,
            self._attr_unique_id,
            state,
        )
        self._attr_available = state is Airtouch5ConnectionStateChange.CONNECTED
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        _LOGGER.debug(
            "async_added_to_hass: entity_id=%s, unique_id=%s",
            self.entity_id,
            self._attr_unique_id,
        )
        self._client.connection_state_callbacks.append(
            self._receive_connection_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener when entity is removed from homeassistant."""
        _LOGGER.debug(
            "async_will_remove_from_hass: entity_id=%s, unique_id=%s",
            self.entity_id,
            self._attr_unique_id,
        )
        self._client.connection_state_callbacks.remove(
            self._receive_connection_callback
        )
