"""Base classes for Hydrawise entities."""

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import SIGNAL_UPDATE_HYDRAWISE


class HydrawiseEntity(Entity):
    """Entity class for Hydrawise devices."""

    _attr_attribution = "Data provided by hydrawise.com"

    def __init__(self, data, description: EntityDescription) -> None:
        """Initialize the Hydrawise entity."""
        self.entity_description = description
        self.data = data
        self._attr_name = f"{self.data['name']} {description.name}"

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_HYDRAWISE, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"identifier": self.data.get("relay")}
