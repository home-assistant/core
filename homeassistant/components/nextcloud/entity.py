"""Base entity for the Nextcloud integration."""
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType

from .const import DOMAIN


class NextcloudEntity(Entity):
    """Base Nextcloud entity."""

    _attr_icon = "mdi:cloud"

    def __init__(self, item: str) -> None:
        """Initialize the Nextcloud entity."""
        self._attr_name = item
        self.item = item
        self._state: StateType = None

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return f"{self.hass.data[DOMAIN]['instance']}#{self.item}"

    def update(self) -> None:
        """Update the sensor."""
        self._state = self.hass.data[DOMAIN][self.item]
