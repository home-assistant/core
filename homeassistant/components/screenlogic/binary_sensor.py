"""Support for a ScreenLogic Binary Sensor."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_MOTION,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import ScreenlogicEntity

import logging

from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    for binary_sensor in hass.data[DOMAIN][config_entry.unique_id]["devices"][
        "binary_sensor"
    ]:
        _LOGGER.debug(binary_sensor)
        entities.append(
            ScreenLogicBinarySensor(
                hass.data[DOMAIN][config_entry.unique_id]["coordinator"], binary_sensor
            )
        )
    async_add_entities(entities, True)


class ScreenLogicBinarySensor(ScreenlogicEntity, BinarySensorEntity):
    """Representation of a ScreenLogic sensor entity"""

    def __init__(self, coordinator, binary_sensor):
        """Initialize of the sensor."""
        super().__init__(coordinator, binary_sensor)

    @property
    def name(self):
        """Return the sensor name"""
        return self.coordinator.data["sensors"][self._entity_id]["name"]

    @property
    def device_class(self):
        """Return the device class."""
        return (
            self.coordinator.data["sensors"][self._entity_id]["hass_type"]
            if "hass_type" in self.coordinator.data["sensors"][self._entity_id]
            else None
        )

    @property
    def is_on(self) -> bool:
        """ Retruns if the sensor is on"""
        return self.coordinator.data["sensors"][self._entity_id]["value"] == 1
