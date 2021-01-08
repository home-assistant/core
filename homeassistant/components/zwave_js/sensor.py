"""Representation of Z-Wave sensors."""

import logging

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave sensor from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_sensor(info: ZwaveDiscoveryInfo):
        """Add Z-Wave Sensor."""
        if info.platform_hint == "string_sensor":
            sensor = ZWaveStringSensor(client, info)
        if info.platform_hint == "numeric_sensor":
            sensor = ZWaveNumericSensor(client, info)
        else:
            LOGGER.warning(
                "Sensor not implemented for %s/%s",
                info.platform_hint,
                info.primary_value.property_name,
            )
            return
        async_add_entities([sensor])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_{SENSOR_DOMAIN}", async_add_sensor)
    )


class ZWaveStringSensor(ZWaveBaseEntity):
    """Representation of a Z-Wave String sensor."""

    @property
    def state(self) -> str:
        """Return state of the sensor."""
        return self.info.primary_value.value

    @property
    def unit_of_measurement(self) -> str:
        """Return unit of measurement the value is expressed in."""
        return self.info.primary_value.metadata.unit


class ZWaveNumericSensor(ZWaveBaseEntity):
    """Representation of a Z-Wave Numeric sensor."""

    @property
    def state(self) -> str:
        """Return state of the sensor."""
        return self.info.primary_value.value

    @property
    def unit_of_measurement(self) -> str:
        """Return unit of measurement the value is expressed in."""
        return self.info.primary_value.metadata.unit
