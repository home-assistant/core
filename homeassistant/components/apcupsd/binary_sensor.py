"""Support for tracking the online status of a UPS."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, VALUE_ONLINE, APCUPSdData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an APCUPSd Online Status binary sensor."""
    data_service = hass.data[DOMAIN][config_entry.entry_id]

    description = BinarySensorEntityDescription(
        key="STATFLAG",
        name="UPS Online Status",
        icon="mdi:heart",
    )

    # If key is not in the "resources" YAML config specified by the user, we set the
    # binary sensor to be disabled by default.
    if (
        CONF_RESOURCES in config_entry.data
        and description.key not in config_entry.data[CONF_RESOURCES]
    ):
        description.entity_registry_enabled_default = False

    async_add_entities(
        [OnlineStatus(data_service, description)], update_before_add=True
    )


class OnlineStatus(BinarySensorEntity):
    """Representation of a UPS online status."""

    def __init__(
        self,
        data_service: APCUPSdData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the APCUPSd binary device."""
        self.entity_description = description
        self._data_service = data_service

    def update(self) -> None:
        """Get the status report from APCUPSd and set this entity's state."""
        self._data_service.update()

        key = self.entity_description.key.upper()
        if key not in self._data_service.status:
            self._attr_is_on = None
            return

        self._attr_is_on = int(self._data_service.status[key], 16) & VALUE_ONLINE > 0
