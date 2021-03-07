"""Platform for binary sensor integration."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubSensorBase

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up binary sensor entities for the binary sensors in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [SmartTubOnline(controller.coordinator, spa) for spa in controller.spas]

    async_add_entities(entities)


class SmartTubOnline(SmartTubSensorBase, BinarySensorEntity):
    """A binary sensor indicating whether the spa is currently online (connected to the cloud)."""

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "Online", "online")

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state is True

    @property
    def device_class(self) -> str:
        """Return the device class for this entity."""
        return DEVICE_CLASS_CONNECTIVITY
