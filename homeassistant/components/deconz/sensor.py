"""Support for deCONZ sensors."""
from pydeconz.sensor import (
    Battery,
    Consumption,
    Daylight,
    Humidity,
    LightLevel,
    Power,
    Pressure,
    Switch,
    Temperature,
    Thermostat,
)

from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_VOLTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import ATTR_DARK, ATTR_ON, NEW_SENSOR
from .deconz_device import DeconzDevice
from .deconz_event import DeconzEvent
from .gateway import get_gateway_from_config_entry

ATTR_CURRENT = "current"
ATTR_POWER = "power"
ATTR_DAYLIGHT = "daylight"
ATTR_EVENT_ID = "event_id"

DEVICE_CLASS = {
    Humidity: DEVICE_CLASS_HUMIDITY,
    LightLevel: DEVICE_CLASS_ILLUMINANCE,
    Power: DEVICE_CLASS_POWER,
    Pressure: DEVICE_CLASS_PRESSURE,
    Temperature: DEVICE_CLASS_TEMPERATURE,
}

ICON = {
    Daylight: "mdi:white-balance-sunny",
    Pressure: "mdi:gauge",
    Temperature: "mdi:thermometer",
}

UNIT_OF_MEASUREMENT = {
    Consumption: ENERGY_KILO_WATT_HOUR,
    Humidity: PERCENTAGE,
    LightLevel: "lx",
    Power: POWER_WATT,
    Pressure: PRESSURE_HPA,
    Temperature: TEMP_CELSIUS,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ platforms."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the deCONZ sensors."""
    gateway = get_gateway_from_config_entry(hass, config_entry)

    batteries = set()
    battery_handler = DeconzBatteryHandler(gateway)

    @callback
    def async_add_sensor(sensors, new=True):
        """Add sensors from deCONZ.

        Create DeconzEvent if part of ZHAType list.
        Create DeconzSensor if not a ZHAType and not a binary sensor.
        Create DeconzBattery if sensor has a battery attribute.
        If new is false it means an existing sensor has got a battery state reported.
        """
        entities = []

        for sensor in sensors:

            if new and sensor.type in Switch.ZHATYPE:

                if gateway.option_allow_clip_sensor or not sensor.type.startswith(
                    "CLIP"
                ):
                    new_event = DeconzEvent(sensor, gateway)
                    hass.async_create_task(new_event.async_update_device_registry())
                    gateway.events.append(new_event)

            elif (
                new
                and sensor.BINARY is False
                and sensor.type not in Battery.ZHATYPE + Thermostat.ZHATYPE
                and (
                    gateway.option_allow_clip_sensor
                    or not sensor.type.startswith("CLIP")
                )
            ):
                entities.append(DeconzSensor(sensor, gateway))

            if sensor.battery is not None:
                new_battery = DeconzBattery(sensor, gateway)
                if new_battery.unique_id not in batteries:
                    batteries.add(new_battery.unique_id)
                    entities.append(new_battery)
                    battery_handler.remove_tracker(sensor)
            else:
                battery_handler.create_tracker(sensor)

        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_SENSOR), async_add_sensor
        )
    )

    async_add_sensor(
        [gateway.api.sensors[key] for key in sorted(gateway.api.sensors, key=int)]
    )


class DeconzSensor(DeconzDevice):
    """Representation of a deCONZ sensor."""

    @callback
    def async_update_callback(self, force_update=False, ignore_update=False):
        """Update the sensor's state."""
        if ignore_update:
            return

        keys = {"on", "reachable", "state"}
        if force_update or self._device.changed_keys.intersection(keys):
            self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.state

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return DEVICE_CLASS.get(type(self._device))

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON.get(type(self._device))

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return UNIT_OF_MEASUREMENT.get(type(self._device))

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

        elif self._device.type in LightLevel.ZHATYPE:

            if self._device.dark is not None:
                attr[ATTR_DARK] = self._device.dark

            if self._device.daylight is not None:
                attr[ATTR_DAYLIGHT] = self._device.daylight

        elif self._device.type in Power.ZHATYPE:
            attr[ATTR_CURRENT] = self._device.current
            attr[ATTR_VOLTAGE] = self._device.voltage

        return attr


class DeconzBattery(DeconzDevice):
    """Battery class for when a device is only represented as an event."""

    @callback
    def async_update_callback(self, force_update=False, ignore_update=False):
        """Update the battery's state, if needed."""
        if ignore_update:
            return

        keys = {"battery", "reachable"}
        if force_update or self._device.changed_keys.intersection(keys):
            self.async_write_ha_state()

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
        return PERCENTAGE

    @property
    def device_state_attributes(self):
        """Return the state attributes of the battery."""
        attr = {}

        if self._device.type in Switch.ZHATYPE:
            for event in self.gateway.events:
                if self._device == event.device:
                    attr[ATTR_EVENT_ID] = event.event_id

        return attr


class DeconzSensorStateTracker:
    """Track sensors without a battery state and signal when battery state exist."""

    def __init__(self, sensor, gateway):
        """Set up tracker."""
        self.sensor = sensor
        self.gateway = gateway
        sensor.register_callback(self.async_update_callback)

    @callback
    def close(self):
        """Clean up tracker."""
        self.sensor.remove_callback(self.async_update_callback)
        self.gateway = None
        self.sensor = None

    @callback
    def async_update_callback(self, ignore_update=False):
        """Sensor state updated."""
        if "battery" in self.sensor.changed_keys:
            async_dispatcher_send(
                self.gateway.hass,
                self.gateway.async_signal_new_device(NEW_SENSOR),
                [self.sensor],
                False,
            )


class DeconzBatteryHandler:
    """Creates and stores trackers for sensors without a battery state."""

    def __init__(self, gateway):
        """Set up battery handler."""
        self.gateway = gateway
        self._trackers = set()

    @callback
    def create_tracker(self, sensor):
        """Create new tracker for battery state."""
        for tracker in self._trackers:
            if sensor == tracker.sensor:
                return
        self._trackers.add(DeconzSensorStateTracker(sensor, self.gateway))

    @callback
    def remove_tracker(self, sensor):
        """Remove tracker of battery state."""
        for tracker in self._trackers:
            if sensor == tracker.sensor:
                tracker.close()
                self._trackers.remove(tracker)
                break
