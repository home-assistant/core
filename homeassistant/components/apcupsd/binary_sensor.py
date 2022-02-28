"""Support for tracking the online status of a UPS."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, KEY_STATUS, VALUE_ONLINE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an APCUPSd Online Status binary sensor."""
    data_service = hass.data[DOMAIN][config_entry.entry_id]

    # If key status is hidden by user, we do not create the binary sensor.
    if (
        CONF_RESOURCES in config_entry.options
        and KEY_STATUS not in config_entry.options[CONF_RESOURCES]
    ):
        return

    async_add_entities([OnlineStatus(data_service)], update_before_add=True)


class OnlineStatus(BinarySensorEntity):
    """Representation of a UPS online status."""

    def __init__(self, data):
        """Initialize the APCUPSd binary device."""
        self._data = data
        self._attr_name = "UPS Online Status"

    def update(self) -> None:
        """Get the status report from APCUPSd and set this entity's state."""
        self._attr_is_on = int(self._data.status[KEY_STATUS], 16) & VALUE_ONLINE > 0
