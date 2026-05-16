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

    async def async_added_to_hass(self) -> None:
        """Register callback with hub."""
        await super().async_added_to_hass()
        self._nobo.register_callback(self._handle_hub_update)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister callback from hub."""
        self._nobo.deregister_callback(self._handle_hub_update)
        await super().async_will_remove_from_hass()

    @callback
    def _handle_hub_update(self, _hub: nobo) -> None:
        """Handle pushed state update from the hub."""
        self._read_state()
        self.async_write_ha_state()

    @callback
    def _read_state(self) -> None:
        """Copy the current hub state from the pynobo client onto the entity attributes.

        The pynobo client keeps its own in-memory state, updated via pushes
        from the hub; subclasses override this to map the relevant values
        onto their `_attr_*` fields. Must be overridden.
        """
        raise NotImplementedError
