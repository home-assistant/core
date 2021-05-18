"""Support for Plaato Airlock sensors."""
from __future__ import annotations

from pyplaato.models.device import PlaatoDevice
from pyplaato.plaato import PlaatoKeg

from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE, SensorEntity
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import ATTR_TEMP, SENSOR_UPDATE
from ...core import callback
from .const import (
    CONF_USE_WEBHOOK,
    COORDINATOR,
    DEVICE,
    DEVICE_ID,
    DOMAIN,
    SENSOR_DATA,
    SENSOR_SIGNAL,
)
from .entity import PlaatoEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Plaato sensor."""


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Plaato from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    @callback
    async def _async_update_from_webhook(device_id, sensor_data: PlaatoDevice):
        """Update/Create the sensors."""
        entry_data[SENSOR_DATA] = sensor_data

        if device_id != entry_data[DEVICE][DEVICE_ID]:
            entry_data[DEVICE][DEVICE_ID] = device_id
            async_add_entities(
                [
                    PlaatoSensor(entry_data, sensor_type)
                    for sensor_type in sensor_data.sensors
                ]
            )
        else:
            for sensor_type in sensor_data.sensors:
                async_dispatcher_send(hass, SENSOR_SIGNAL % (device_id, sensor_type))

    if entry.data[CONF_USE_WEBHOOK]:
        async_dispatcher_connect(hass, SENSOR_UPDATE, _async_update_from_webhook)
    else:
        coordinator = entry_data[COORDINATOR]
        async_add_entities(
            PlaatoSensor(entry_data, sensor_type, coordinator)
            for sensor_type in coordinator.data.sensors
        )


class PlaatoSensor(PlaatoEntity, SensorEntity):
    """Representation of a Plaato Sensor."""

    @property
    def device_class(self) -> str | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        if (
            self._coordinator is not None
            and self._sensor_type == PlaatoKeg.Pins.TEMPERATURE
        ):
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
