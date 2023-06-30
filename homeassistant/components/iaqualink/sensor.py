"""Support for Aqualink temperature sensors."""
from __future__ import annotations

from homeassistant.components.sensor import DOMAIN, SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AqualinkEntity
from .const import DOMAIN as AQUALINK_DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    def native_unit_of_measurement(self) -> str | None:
        """Return the measurement unit for the sensor."""
        if self.dev.name.endswith("_temp"):
            if self.dev.system.temp_unit == "F":
                return UnitOfTemperature.FAHRENHEIT
            return UnitOfTemperature.CELSIUS
        return None

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if self.dev.state == "":
            return None

        try:
            return int(self.dev.state)
        except ValueError:
            return float(self.dev.state)

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of the sensor."""
        if self.dev.name.endswith("_temp"):
            return SensorDeviceClass.TEMPERATURE
        return None
