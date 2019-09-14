"""Support for deCONZ sensors."""
from pydeconz.sensor import Consumption, Daylight, LightLevel, Power, Switch

from homeassistant.const import ATTR_TEMPERATURE, ATTR_VOLTAGE, DEVICE_CLASS_BATTERY
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import ATTR_DARK, ATTR_ON, NEW_SENSOR
from .deconz_device import DeconzDevice
from .deconz_event import DeconzEvent
from .gateway import get_gateway_from_config_entry, DeconzEntityHandler

ATTR_CURRENT = "current"
ATTR_POWER = "power"
ATTR_DAYLIGHT = "daylight"
ATTR_EVENT_ID = "event_id"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ platforms."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ sensors."""
    gateway = get_gateway_from_config_entry(hass, config_entry)

    batteries = set()
    entity_handler = DeconzEntityHandler(gateway)

    @callback
    def async_add_sensor(sensors):
        """Add sensors from deCONZ.

        Create DeconzEvent if part of ZHAType list.
        Create DeconzSensor if not a ZHAType and not a binary sensor.
        Create DeconzBattery if sensor has a battery attribute.
        """
        entities = []

        for sensor in sensors:

            if sensor.type in Switch.ZHATYPE:

                if gateway.option_allow_clip_sensor or not sensor.type.startswith(
                    "CLIP"
                ):
                    new_event = DeconzEvent(sensor, gateway)
                    hass.async_create_task(new_event.async_update_device_registry())
                    gateway.events.append(new_event)

            elif not sensor.BINARY:

                new_sensor = DeconzSensor(sensor, gateway)
                entity_handler.add_entity(new_sensor)
                entities.append(new_sensor)

            if sensor.battery:
                new_battery = DeconzBattery(sensor, gateway)
                if new_battery.unique_id not in batteries:
                    batteries.add(new_battery.unique_id)
                    entities.append(new_battery)

        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_SENSOR), async_add_sensor
        )
    )

    async_add_sensor(gateway.api.sensors.values())


class DeconzSensor(DeconzDevice):
    """Representation of a deCONZ sensor."""

    @callback
    def async_update_callback(self, force_update=False):
        """Update the sensor's state."""
        changed = set(self._device.changed_keys)
        keys = {"on", "reachable", "state"}
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

    @callback
    def async_update_callback(self, force_update=False):
        """Update the battery's state, if needed."""
        changed = set(self._device.changed_keys)
        keys = {"battery", "reachable"}
        if force_update or any(key in changed for key in keys):
            self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return f"{self.serial}-battery"

    @property
    def state(self):
        """Return the state of the battery."""
        return self._device.battery

    @property
    def name(self):
        """Return the name of the battery."""
        return f"{self._device.name} Battery Level"

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return "%"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the battery."""
        attr = {}

        if self._device.type in Switch.ZHATYPE:
            for event in self.gateway.events:
                if self._device == event.device:
                    attr[ATTR_EVENT_ID] = event.event_id

        return attr
