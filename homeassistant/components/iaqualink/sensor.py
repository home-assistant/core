"""Support for Aqualink temperature sensors."""

from __future__ import annotations

from iaqualink.device import AqualinkSensor

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import AqualinkEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up discovered sensors."""
    async_add_entities(
        (HassAqualinkSensor(dev) for dev in hass.data[DOMAIN][SENSOR_DOMAIN]),
        True,
    )


class HassAqualinkSensor(AqualinkEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(self, dev: AqualinkSensor) -> None:
        """Initialize AquaLink sensor."""
        super().__init__(dev)
        self._attr_name = dev.label
        if not dev.name.endswith("_temp"):
            return
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        if dev.system.temp_unit == "F":
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
            return
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        if self.dev.state == "":
            return None

        try:
            return int(self.dev.state)
        except ValueError:
            return float(self.dev.state)
