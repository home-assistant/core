"""Sensor reporting on the shopping list items."""
import logging

from homeassistant.helpers.entity import Entity

from . import EVENT
from .const import DOMAIN

ATTR_ITEMS = "items"
NAME_SENSOR = "Shopping List"


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the shopping list sensor."""
    await async_add_entities([ShoppingListEntity(hass)], True)


class ShoppingListEntity(Entity):
    """Representation of the shopping list sensor."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self._hass = hass
        self._items = []

        hass.bus.async_listen(EVENT, self._update)

    def _update(self, _):
        """Update the state on the `shopping_list_updated` signal."""
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self) -> bool:
        """We update only based on change events."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return NAME_SENSOR

    @property
    def state(self):
        """Return number of items in the shopping list."""
        return len(self._items)

    @property
    def icon(self):
        """Return the frontend icon for the shopping list."""
        return "mdi:cart"

    async def async_update(self):
        """Update the items."""
        self._items = self._hass.data[DOMAIN].items

    @property
    def device_state_attributes(self):
        """Entries in shopping list."""
        items_attr = ",".join([x["name"] for x in self._items])
        return {"items": items_attr}
