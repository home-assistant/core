"""Support for Soma sensors."""
from datetime import timedelta
import logging

from requests import RequestException

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE
from homeassistant.util import Throttle

from . import DEVICES, SomaEntity
from .const import API, DOMAIN

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Soma sensor platform."""

    devices = hass.data[DOMAIN][DEVICES]

    async_add_entities(
        [SomaSensor(sensor, hass.data[DOMAIN][API]) for sensor in devices], True
    )


class SomaSensor(SomaEntity, SensorEntity):
    """Representation of a Soma cover device."""

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_BATTERY

    @property
    def name(self):
        """Return the name of the device."""
        return self.device["name"] + " battery level"

    @property
    def state(self):
        """Return the state of the entity."""
        return self.battery_state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return PERCENTAGE

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update the sensor with the latest data."""
        try:
            _LOGGER.debug("Soma Sensor Update")
            response = await self.hass.async_add_executor_job(
                self.api.get_battery_level, self.device["mac"]
            )
        except RequestException:
            _LOGGER.error("Connection to SOMA Connect failed")
            self.is_available = False
            return
        if response["result"] != "success":
            _LOGGER.error(
                "Unable to reach device %s (%s)", self.device["name"], response["msg"]
            )
            self.is_available = False
            return
        # https://support.somasmarthome.com/hc/en-us/articles/360026064234-HTTP-API
        # battery_level response is expected to be min = 360, max 410 for
        # 0-100% levels above 410 are consider 100% and below 360, 0% as the
        # device considers 360 the minimum to move the motor.
        _battery = round(2 * (response["battery_level"] - 360))
        battery = max(min(100, _battery), 0)
        self.battery_state = battery
        self.is_available = True
