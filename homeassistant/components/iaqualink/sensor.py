"""Support for Aqualink temperature sensors."""
from __future__ import annotations

from homeassistant.components.sensor import DOMAIN, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant

from . import AqualinkEntity
from .const import DOMAIN as AQUALINK_DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up discovered sensors."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkSensor(dev))
    async_add_entities(devs, True)


class HassAqualinkSensor(AqualinkEntity, SensorEntity):
    """Representation of a sensor."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.dev.label

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the measurement unit for the sensor."""
        if self.dev.name.endswith("_temp"):
            if self.dev.system.temp_unit == "F":
                return TEMP_FAHRENHEIT
            return TEMP_CELSIUS
        return None

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if self.dev.state == "":
            return None

        try:
            state = int(self.dev.state)
        except ValueError:
            state = float(self.dev.state)
        return state

    @property
    def device_class(self) -> str | None:
        """Return the class of the sensor."""
        if self.dev.name.endswith("_temp"):
            return DEVICE_CLASS_TEMPERATURE
        return None
