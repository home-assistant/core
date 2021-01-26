"""Support for Plaato Airlock sensors."""

import logging
from typing import Optional

from pyplaato.models.device import PlaatoDevice
from pyplaato.plaato import PlaatoKeg

from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import ATTR_TEMP, SENSOR_UPDATE
from .const import CONF_USE_WEBHOOK, COORDINATOR, DEVICE, DEVICE_ID, DOMAIN, SENSOR_DATA
from .entity import PlaatoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Plaato sensor."""


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Plaato from a config entry."""
    devices = {}

    async def _update_sensor(device_id, sensor_data: PlaatoDevice):
        """Update/Create the sensors."""
        entry_data = hass.data[DOMAIN][entry.entry_id]
        entry_data[SENSOR_DATA] = sensor_data

        if entry.entry_id not in devices:
            entry_data[DEVICE][DEVICE_ID] = device_id

            entities = [
                PlaatoSensor(hass.data[DOMAIN][entry.entry_id], sensor_type)
                for sensor_type in sensor_data.sensors.keys()
            ]
            devices[entry.entry_id] = entities
            async_add_entities(entities)
        else:
            for entity in devices[entry.entry_id]:
                async_dispatcher_send(hass, f"{DOMAIN}_{entity.unique_id}")

    if entry.data.get(CONF_USE_WEBHOOK, False):
        async_dispatcher_connect(hass, SENSOR_UPDATE, _update_sensor)
    else:
        coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
        async_add_entities(
            PlaatoSensor(hass.data[DOMAIN][entry.entry_id], sensor_type, coordinator)
            for sensor_type in coordinator.data.sensors.keys()
        )

    return True


class PlaatoSensor(PlaatoEntity):
    """Representation of a Plaato Sensor."""

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self._coordinator is not None:
            if self._sensor_type == PlaatoKeg.Pins.TEMPERATURE:
                return DEVICE_CLASS_TEMPERATURE
        if self._sensor_type == ATTR_TEMP:
            return DEVICE_CLASS_TEMPERATURE
        return None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._sensor_data.sensors.get(self._sensor_type)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor_data.get_unit_of_measurement(self._sensor_type)
