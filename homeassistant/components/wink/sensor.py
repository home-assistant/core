"""Support for Wink sensors."""
from contextlib import suppress
import logging

import pywink

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEGREE, TEMP_CELSIUS

from . import DOMAIN, WinkDevice

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = ["temperature", "humidity", "balance", "proximity"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink platform."""

    for sensor in pywink.get_sensors():
        _id = sensor.object_id() + sensor.name()
        if (
            _id not in hass.data[DOMAIN]["unique_ids"]
            and sensor.capability() in SENSOR_TYPES
        ):
            add_entities([WinkSensorEntity(sensor, hass)])

    for eggtray in pywink.get_eggtrays():
        _id = eggtray.object_id() + eggtray.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkSensorEntity(eggtray, hass)])

    for tank in pywink.get_propane_tanks():
        _id = tank.object_id() + tank.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkSensorEntity(tank, hass)])

    for piggy_bank in pywink.get_piggy_banks():
        _id = piggy_bank.object_id() + piggy_bank.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            try:
                if piggy_bank.capability() in SENSOR_TYPES:
                    add_entities([WinkSensorEntity(piggy_bank, hass)])
            except AttributeError:
                _LOGGER.info("Device is not a sensor")


class WinkSensorEntity(WinkDevice, SensorEntity):
    """Representation of a Wink sensor."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        super().__init__(wink, hass)
        self.capability = self.wink.capability()
        if self.wink.unit() == DEGREE:
            self._unit_of_measurement = TEMP_CELSIUS
        else:
            self._unit_of_measurement = self.wink.unit()

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]["entities"]["sensor"].append(self)

    @property
    def native_value(self):
        """Return the state."""
        state = None
        if self.capability == "humidity":
            if self.wink.state() is not None:
                state = round(self.wink.state())
        elif self.capability == "temperature":
            if self.wink.state() is not None:
                state = round(self.wink.state(), 1)
        elif self.capability == "balance":
            if self.wink.state() is not None:
                state = round(self.wink.state() / 100, 2)
        elif self.capability == "proximity":
            if self.wink.state() is not None:
                state = self.wink.state()
        else:
            state = self.wink.state()
        return state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        super_attrs = super().extra_state_attributes

        # Ignore error, this sensor isn't an eggminder
        with suppress(AttributeError):
            super_attrs["egg_times"] = self.wink.eggs()

        return super_attrs
