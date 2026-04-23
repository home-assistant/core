"""Base entity for the Nobø Ecohub integration."""

from pynobo import nobo

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity


class NoboBaseEntity(Entity):
    """Base class for Nobø Ecohub entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: nobo) -> None:
        """Initialize the entity."""
        self._nobo = hub
        self._attr_available = hub.connected

    async def async_added_to_hass(self) -> None:
        """Register callbacks with hub."""
        await super().async_added_to_hass()
        self._nobo.register_callback(self._handle_hub_update)
        self._nobo.register_connection_callback(self._handle_hub_connection)
        # Resync in case the state changed between __init__ and callback registration.
        self._attr_available = self._nobo.connected

    async def async_will_remove_from_hass(self) -> None:
        """Deregister callbacks from hub."""
        self._nobo.deregister_connection_callback(self._handle_hub_connection)
        self._nobo.deregister_callback(self._handle_hub_update)
        await super().async_will_remove_from_hass()

    @callback
    def _handle_hub_update(self, _hub: nobo) -> None:
        """Handle pushed state update from the hub."""
        self._read_state()
        self.async_write_ha_state()

    @callback
    def _handle_hub_connection(self, _hub: nobo, connected: bool) -> None:
        """Handle a connection-state transition from the hub."""
        self._attr_available = connected
        if connected:
            # Refresh state values so the first state write after reconnect
            # carries fresh data, not whatever was cached pre-disconnect.
            self._read_state()
        self.async_write_ha_state()

    @callback
    def _read_state(self) -> None:
        """Read the current state from the hub. Must be overridden."""
        raise NotImplementedError
