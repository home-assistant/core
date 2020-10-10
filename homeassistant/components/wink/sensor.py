"""Support for Wink sensors."""
import logging

import pywink

from homeassistant.const import DEGREE, TEMP_CELSIUS

from . import DOMAIN, WinkDevice

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = ["temperature", "humidity", "balance", "proximity"]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink platform."""

    for sensor in pywink.get_sensors():
        _id = sensor.object_id() + sensor.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            if sensor.capability() in SENSOR_TYPES:
                add_entities([WinkSensorDevice(sensor, hass)])

    for eggtray in pywink.get_eggtrays():
        _id = eggtray.object_id() + eggtray.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkSensorDevice(eggtray, hass)])

    for tank in pywink.get_propane_tanks():
        _id = tank.object_id() + tank.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkSensorDevice(tank, hass)])

    for piggy_bank in pywink.get_piggy_banks():
        _id = piggy_bank.object_id() + piggy_bank.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            try:
                if piggy_bank.capability() in SENSOR_TYPES:
                    add_entities([WinkSensorDevice(piggy_bank, hass)])
            except AttributeError:
                _LOGGER.info("Device is not a sensor")


class WinkSensorDevice(WinkDevice):
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
    def state(self):
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
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        super_attrs = super().device_state_attributes
        try:
            super_attrs["egg_times"] = self.wink.eggs()
        except AttributeError:
            # Ignore error, this sensor isn't an eggminder
            pass
        return super_attrs
