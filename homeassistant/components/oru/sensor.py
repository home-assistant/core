"""Platform for sensor integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from oru import Meter, MeterError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_METER_NUMBER = "meter_number"

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_METER_NUMBER): cv.string}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    meter_number = config[CONF_METER_NUMBER]

    try:
        meter = Meter(meter_number)

    except MeterError:
        _LOGGER.error("Unable to create Oru meter")
        return

    add_entities([CurrentEnergyUsageSensor(meter)], True)

    _LOGGER.debug("Oru meter_number = %s", meter_number)


class CurrentEnergyUsageSensor(SensorEntity):
    """Representation of the sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_name = "ORU Current Energy Usage"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, meter):
        """Initialize the sensor."""
        self._available = None
        self.meter = meter

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self.meter.meter_id

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            last_read = self.meter.last_read()

            self._attr_native_value = last_read
            self._available = True

            _LOGGER.debug(
                "%s = %s %s",
                self.name,
                self.native_value,
                self.native_unit_of_measurement,
            )
        except MeterError as err:
            self._available = False

            _LOGGER.error("Unexpected oru meter error: %s", err)
