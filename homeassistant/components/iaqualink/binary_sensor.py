"""Support for Aqualink temperature sensors."""
import logging

from iaqualink import AqualinkBinarySensor

from homeassistant.components.binary_sensor import (
    BinarySensorDevice,
    DEVICE_CLASS_COLD,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import AqualinkEntityMixin
from .const import DOMAIN as AQUALINK_DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up discovered binary sensors."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkBinarySensor(dev))
    async_add_entities(devs, True)


class HassAqualinkBinarySensor(BinarySensorDevice, AqualinkEntityMixin):
    """Representation of a binary sensor."""

    def __init__(self, dev: AqualinkBinarySensor):
        """Initialize the binary sensor."""
        self.dev = dev

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return self.dev.label

    @property
    def is_on(self) -> bool:
        """Return whether the binary sensor is on or not."""
        return self.dev.is_on

    @property
    def device_class(self) -> str:
        """Return the class of the binary sensor."""
        if self.name == "Freeze Protection":
            return DEVICE_CLASS_COLD
        return None
