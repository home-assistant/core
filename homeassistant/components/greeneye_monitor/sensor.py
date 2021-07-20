"""Support for the sensors in a GreenEye Monitor."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_SENSOR_TYPE,
    CONF_TEMPERATURE_UNIT,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_POTENTIAL_VOLT,
    POWER_WATT,
    TIME_HOURS,
    TIME_MINUTES,
    TIME_SECONDS,
)

from . import (
    CONF_COUNTED_QUANTITY,
    CONF_COUNTED_QUANTITY_PER_PULSE,
    CONF_MONITOR_SERIAL_NUMBER,
    CONF_NET_METERING,
    CONF_NUMBER,
    CONF_TIME_UNIT,
    DATA_GREENEYE_MONITOR,
    SENSOR_TYPE_CURRENT,
    SENSOR_TYPE_PULSE_COUNTER,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPE_VOLTAGE,
)

DATA_PULSES = "pulses"
DATA_WATT_SECONDS = "watt_seconds"

UNIT_WATTS = POWER_WATT

COUNTER_ICON = "mdi:counter"
CURRENT_SENSOR_ICON = "mdi:flash"
TEMPERATURE_ICON = "mdi:thermometer"
VOLTAGE_ICON = "mdi:current-ac"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a single GEM temperature sensor."""
    if not discovery_info:
        return

    entities = []
    for sensor in discovery_info:
        sensor_type = sensor[CONF_SENSOR_TYPE]
        if sensor_type == SENSOR_TYPE_CURRENT:
            entities.append(
                CurrentSensor(
                    sensor[CONF_MONITOR_SERIAL_NUMBER],
                    sensor[CONF_NUMBER],
                    sensor[CONF_NAME],
                    sensor[CONF_NET_METERING],
                )
            )
        elif sensor_type == SENSOR_TYPE_PULSE_COUNTER:
            entities.append(
                PulseCounter(
                    sensor[CONF_MONITOR_SERIAL_NUMBER],
                    sensor[CONF_NUMBER],
                    sensor[CONF_NAME],
                    sensor[CONF_COUNTED_QUANTITY],
                    sensor[CONF_TIME_UNIT],
                    sensor[CONF_COUNTED_QUANTITY_PER_PULSE],
                )
            )
        elif sensor_type == SENSOR_TYPE_TEMPERATURE:
            entities.append(
                TemperatureSensor(
                    sensor[CONF_MONITOR_SERIAL_NUMBER],
                    sensor[CONF_NUMBER],
                    sensor[CONF_NAME],
                    sensor[CONF_TEMPERATURE_UNIT],
                )
            )
        elif sensor_type == SENSOR_TYPE_VOLTAGE:
            entities.append(
                VoltageSensor(
                    sensor[CONF_MONITOR_SERIAL_NUMBER],
                    sensor[CONF_NUMBER],
                    sensor[CONF_NAME],
                )
            )

    async_add_entities(entities)


class GEMSensor(SensorEntity):
    """Base class for GreenEye Monitor sensors."""

    _attr_should_poll = False

    def __init__(self, monitor_serial_number, name, sensor_type, number):
        """Construct the entity."""
        self._monitor_serial_number = monitor_serial_number
        self._name = name
        self._sensor = None
        self._sensor_type = sensor_type
        self._number = number

    @property
    def unique_id(self):
        """Return a unique ID for this sensor."""
        return f"{self._monitor_serial_number}-{self._sensor_type}-{self._number}"

    @property
    def name(self):
        """Return the name of the channel."""
        return self._name

    async def async_added_to_hass(self):
        """Wait for and connect to the sensor."""
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]

        if not self._try_connect_to_monitor(monitors):
            monitors.add_listener(self._on_new_monitor)

    def _on_new_monitor(self, *args):
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]
        if self._try_connect_to_monitor(monitors):
            monitors.remove_listener(self._on_new_monitor)

    async def async_will_remove_from_hass(self):
        """Remove listener from the sensor."""
        if self._sensor:
            self._sensor.remove_listener(self.async_write_ha_state)
        else:
            monitors = self.hass.data[DATA_GREENEYE_MONITOR]
            monitors.remove_listener(self._on_new_monitor)

    def _try_connect_to_monitor(self, monitors):
        monitor = monitors.monitors.get(self._monitor_serial_number)
        if not monitor:
            return False

        self._sensor = self._get_sensor(monitor)
        self._sensor.add_listener(self.async_write_ha_state)

        return True

    def _get_sensor(self, monitor):
        raise NotImplementedError()


class CurrentSensor(GEMSensor):
    """Entity showing power usage on one channel of the monitor."""

    _attr_icon = CURRENT_SENSOR_ICON
    _attr_unit_of_measurement = UNIT_WATTS

    def __init__(self, monitor_serial_number, number, name, net_metering):
        """Construct the entity."""
        super().__init__(monitor_serial_number, name, "current", number)
        self._net_metering = net_metering

    def _get_sensor(self, monitor):
        return monitor.channels[self._number - 1]

    @property
    def state(self):
        """Return the current number of watts being used by the channel."""
        if not self._sensor:
            return None

        return self._sensor.watts

    @property
    def extra_state_attributes(self):
        """Return total wattseconds in the state dictionary."""
        if not self._sensor:
            return None

        if self._net_metering:
            watt_seconds = self._sensor.polarized_watt_seconds
        else:
            watt_seconds = self._sensor.absolute_watt_seconds

        return {DATA_WATT_SECONDS: watt_seconds}


class PulseCounter(GEMSensor):
    """Entity showing rate of change in one pulse counter of the monitor."""

    _attr_icon = COUNTER_ICON

    def __init__(
        self,
        monitor_serial_number,
        number,
        name,
        counted_quantity,
        time_unit,
        counted_quantity_per_pulse,
    ):
        """Construct the entity."""
        super().__init__(monitor_serial_number, name, "pulse", number)
        self._counted_quantity = counted_quantity
        self._counted_quantity_per_pulse = counted_quantity_per_pulse
        self._time_unit = time_unit

    def _get_sensor(self, monitor):
        return monitor.pulse_counters[self._number - 1]

    @property
    def state(self):
        """Return the current rate of change for the given pulse counter."""
        if not self._sensor or self._sensor.pulses_per_second is None:
            return None

        return (
            self._sensor.pulses_per_second
            * self._counted_quantity_per_pulse
            * self._seconds_per_time_unit
        )

    @property
    def _seconds_per_time_unit(self):
        """Return the number of seconds in the given display time unit."""
        if self._time_unit == TIME_SECONDS:
            return 1
        if self._time_unit == TIME_MINUTES:
            return 60
        if self._time_unit == TIME_HOURS:
            return 3600

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this pulse counter."""
        return f"{self._counted_quantity}/{self._time_unit}"

    @property
    def extra_state_attributes(self):
        """Return total pulses in the data dictionary."""
        if not self._sensor:
            return None

        return {DATA_PULSES: self._sensor.pulses}


class TemperatureSensor(GEMSensor):
    """Entity showing temperature from one temperature sensor."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_icon = TEMPERATURE_ICON

    def __init__(self, monitor_serial_number, number, name, unit):
        """Construct the entity."""
        super().__init__(monitor_serial_number, name, "temp", number)
        self._unit = unit

    def _get_sensor(self, monitor):
        return monitor.temperature_sensors[self._number - 1]

    @property
    def state(self):
        """Return the current temperature being reported by this sensor."""
        if not self._sensor:
            return None

        return self._sensor.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this sensor (user specified)."""
        return self._unit


class VoltageSensor(GEMSensor):
    """Entity showing voltage."""

    _attr_icon = VOLTAGE_ICON
    _attr_unit_of_measurement = ELECTRIC_POTENTIAL_VOLT

    def __init__(self, monitor_serial_number, number, name):
        """Construct the entity."""
        super().__init__(monitor_serial_number, name, "volts", number)

    def _get_sensor(self, monitor):
        """Wire the updates to the monitor itself, since there is no voltage element in the API."""
        return monitor

    @property
    def state(self):
        """Return the current voltage being reported by this sensor."""
        if not self._sensor:
            return None

        return self._sensor.voltage
