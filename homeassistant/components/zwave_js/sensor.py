"""Representation of Z-Wave sensors."""

import logging

from zwave_js_server.const import CommandClass

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave sensor from config entry."""

    @callback
    def async_add_sensor(info: ZwaveDiscoveryInfo):
        """Add Z-Wave Sensor."""
        if info.platform_hint == "string_sensor":
            sensor = ZWaveStringSensor(info)
        else:
            _LOGGER.warning(
                "Sensor not implemented for %s/%s",
                info.platform_hint,
                info.primary_value.property_name,
            )
            return

        async_add_entities([sensor])

    async_dispatcher_connect(hass, f"{DOMAIN}_new_{SENSOR_DOMAIN}", async_add_sensor)


class ZWaveStringSensor(ZWaveBaseEntity):
    """Representation of a Z-Wave String sensor."""

    @property
    def state(self):
        """Return state of the sensor."""
        return self.info.primary_value.value

    @property
    def unit_of_measurement(self):
        """Return unit of measurement the value is expressed in."""
        return self.info.primary_value.unit
