"""Support for Aqualink temperature sensors."""
import logging
from typing import Optional

from homeassistant.components.sensor import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.typing import HomeAssistantType

from . import AqualinkEntity
from .const import DOMAIN as AQUALINK_DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up discovered sensors."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkSensor(dev))
    async_add_entities(devs, True)


class HassAqualinkSensor(AqualinkEntity):
    """Representation of a sensor."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.dev.label

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the measurement unit for the sensor."""
        if self.dev.name.endswith("_temp"):
            if self.dev.system.temp_unit == "F":
                return TEMP_FAHRENHEIT
            return TEMP_CELSIUS
        return None

    @property
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        if self.dev.state == "":
            return None

        try:
            state = int(self.dev.state)
        except ValueError:
            state = float(self.dev.state)
        return state

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of the sensor."""
        if self.dev.name.endswith("_temp"):
            return DEVICE_CLASS_TEMPERATURE
        return None
