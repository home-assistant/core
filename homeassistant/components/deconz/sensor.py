"""Support for deCONZ sensors."""
from pydeconz.sensor import Consumption, Daylight, LightLevel, Power, Switch

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    DEVICE_CLASS_BATTERY,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from .const import ATTR_DARK, ATTR_ON, NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

ATTR_CURRENT = "current"
ATTR_POWER = "power"
ATTR_DAYLIGHT = "daylight"
ATTR_EVENT_ID = "event_id"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ platforms."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ sensors."""
    gateway = get_gateway_from_config_entry(hass, config_entry)

    @callback
    def async_add_sensor(sensors):
        """Add sensors from deCONZ."""
        entities = []

        for sensor in sensors:

            if not sensor.BINARY and not (
                not gateway.allow_clip_sensor and sensor.type.startswith("CLIP")
            ):

                if sensor.type in Switch.ZHATYPE:
                    if sensor.battery:
                        entities.append(DeconzBattery(sensor, gateway))

                else:
                    entities.append(DeconzSensor(sensor, gateway))

        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_event_new_device(NEW_SENSOR), async_add_sensor
        )
    )

    async_add_sensor(gateway.api.sensors.values())


class DeconzSensor(DeconzDevice):
    """Representation of a deCONZ sensor."""

    @callback
    def async_update_callback(self, force_update=False):
        """Update the sensor's state."""
        changed = set(self._device.changed_keys)
        keys = {"battery", "on", "reachable", "state"}
        if force_update or any(key in changed for key in keys):
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.state

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device.SENSOR_CLASS

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._device.SENSOR_ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return self._device.SENSOR_UNIT

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {}
        if self._device.battery:
            attr[ATTR_BATTERY_LEVEL] = self._device.battery

        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on

        if self._device.secondary_temperature is not None:
            attr[ATTR_TEMPERATURE] = self._device.secondary_temperature

        if self._device.type in Consumption.ZHATYPE:
            attr[ATTR_POWER] = self._device.power

        elif self._device.type in Daylight.ZHATYPE:
            attr[ATTR_DAYLIGHT] = self._device.daylight

        elif self._device.type in LightLevel.ZHATYPE and self._device.dark is not None:
            attr[ATTR_DARK] = self._device.dark

        elif self._device.type in Power.ZHATYPE:
            attr[ATTR_CURRENT] = self._device.current
            attr[ATTR_VOLTAGE] = self._device.voltage

        return attr


class DeconzBattery(DeconzDevice):
    """Battery class for when a device is only represented as an event."""

    def __init__(self, device, gateway):
        """Register dispatcher callback for update of battery state."""
        super().__init__(device, gateway)

        self._name = "{} {}".format(self._device.name, "Battery Level")
        self._unit_of_measurement = "%"

    @callback
    def async_update_callback(self, force_update=False):
        """Update the battery's state, if needed."""
        changed = set(self._device.changed_keys)
        keys = {"battery", "reachable"}
        if force_update or any(key in changed for key in keys):
            self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the battery."""
        return self._device.battery

    @property
    def name(self):
        """Return the name of the battery."""
        return self._name

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the battery."""
        attr = {ATTR_EVENT_ID: slugify(self._device.name)}
        return attr
