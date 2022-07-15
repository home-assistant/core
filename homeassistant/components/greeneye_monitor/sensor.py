"""Support for the sensors in a GreenEye Monitor."""
from __future__ import annotations

from typing import Any, Union

import greeneye

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_SENSORS,
    CONF_TEMPERATURE_UNIT,
    ELECTRIC_POTENTIAL_VOLT,
    POWER_WATT,
    TIME_HOURS,
    TIME_MINUTES,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_CHANNELS,
    CONF_COUNTED_QUANTITY,
    CONF_COUNTED_QUANTITY_PER_PULSE,
    CONF_MONITORS,
    CONF_NET_METERING,
    CONF_NUMBER,
    CONF_PULSE_COUNTERS,
    CONF_SERIAL_NUMBER,
    CONF_TEMPERATURE_SENSORS,
    CONF_TIME_UNIT,
    CONF_VOLTAGE_SENSORS,
    DATA_GREENEYE_MONITOR,
)

DATA_PULSES = "pulses"
DATA_WATT_SECONDS = "watt_seconds"

UNIT_WATTS = POWER_WATT

COUNTER_ICON = "mdi:counter"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a single GEM temperature sensor."""
    if not discovery_info:
        return

    monitor_configs = discovery_info[CONF_MONITORS]

    def on_new_monitor(monitor: greeneye.monitor.Monitor) -> None:
        monitor_config = next(
            filter(
                lambda monitor_config: monitor_config[CONF_SERIAL_NUMBER]
                == monitor.serial_number,
                monitor_configs,
            ),
            None,
        )
        if monitor_config:
            entities: list[GEMSensor] = []

            channel_configs = monitor_config[CONF_CHANNELS]
            for sensor in channel_configs:
                entities.append(
                    CurrentSensor(
                        monitor,
                        sensor[CONF_NUMBER],
                        sensor[CONF_NAME],
                        sensor[CONF_NET_METERING],
                    )
                )

            pulse_counter_configs = monitor_config[CONF_PULSE_COUNTERS]
            for sensor in pulse_counter_configs:
                entities.append(
                    PulseCounter(
                        monitor,
                        sensor[CONF_NUMBER],
                        sensor[CONF_NAME],
                        sensor[CONF_COUNTED_QUANTITY],
                        sensor[CONF_TIME_UNIT],
                        sensor[CONF_COUNTED_QUANTITY_PER_PULSE],
                    )
                )

            temperature_sensor_configs = monitor_config[CONF_TEMPERATURE_SENSORS]
            for sensor in temperature_sensor_configs[CONF_SENSORS]:
                entities.append(
                    TemperatureSensor(
                        monitor,
                        sensor[CONF_NUMBER],
                        sensor[CONF_NAME],
                        temperature_sensor_configs[CONF_TEMPERATURE_UNIT],
                    )
                )

            voltage_sensor_configs = monitor_config[CONF_VOLTAGE_SENSORS]
            for sensor in voltage_sensor_configs:
                entities.append(
                    VoltageSensor(monitor, sensor[CONF_NUMBER], sensor[CONF_NAME])
                )

            async_add_entities(entities)
            monitor_configs.remove(monitor_config)

        if len(monitor_configs) == 0:
            monitors.remove_listener(on_new_monitor)

    monitors: greeneye.Monitors = hass.data[DATA_GREENEYE_MONITOR]
    monitors.add_listener(on_new_monitor)
    for monitor in monitors.monitors.values():
        on_new_monitor(monitor)


UnderlyingSensorType = Union[
    greeneye.monitor.Channel,
    greeneye.monitor.PulseCounter,
    greeneye.monitor.TemperatureSensor,
    greeneye.monitor.VoltageSensor,
]


class GEMSensor(SensorEntity):
    """Base class for GreenEye Monitor sensors."""

    _attr_should_poll = False

    def __init__(
        self,
        monitor: greeneye.monitor.Monitor,
        name: str,
        sensor_type: str,
        sensor: UnderlyingSensorType,
        number: int,
    ) -> None:
        """Construct the entity."""
        self._monitor = monitor
        self._monitor_serial_number = self._monitor.serial_number
        self._attr_name = name
        self._sensor_type = sensor_type
        self._sensor: UnderlyingSensorType = sensor
        self._number = number
        self._attr_unique_id = (
            f"{self._monitor_serial_number}-{self._sensor_type}-{self._number}"
        )

    async def async_added_to_hass(self) -> None:
        """Wait for and connect to the sensor."""
        self._sensor.add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Remove listener from the sensor."""
        if self._sensor:
            self._sensor.remove_listener(self.async_write_ha_state)


class CurrentSensor(GEMSensor):
    """Entity showing power usage on one channel of the monitor."""

    _attr_native_unit_of_measurement = UNIT_WATTS
    _attr_device_class = SensorDeviceClass.POWER

    def __init__(
        self,
        monitor: greeneye.monitor.Monitor,
        number: int,
        name: str,
        net_metering: bool,
    ) -> None:
        """Construct the entity."""
        super().__init__(monitor, name, "current", monitor.channels[number - 1], number)
        self._sensor: greeneye.monitor.Channel = self._sensor
        self._net_metering = net_metering

    @property
    def native_value(self) -> float | None:
        """Return the current number of watts being used by the channel."""
        return self._sensor.watts

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return total wattseconds in the state dictionary."""
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
        monitor: greeneye.monitor.Monitor,
        number: int,
        name: str,
        counted_quantity: str,
        time_unit: str,
        counted_quantity_per_pulse: float,
    ) -> None:
        """Construct the entity."""
        super().__init__(
            monitor, name, "pulse", monitor.pulse_counters[number - 1], number
        )
        self._sensor: greeneye.monitor.PulseCounter = self._sensor
        self._counted_quantity_per_pulse = counted_quantity_per_pulse
        self._time_unit = time_unit
        self._attr_native_unit_of_measurement = f"{counted_quantity}/{self._time_unit}"

    @property
    def native_value(self) -> float | None:
        """Return the current rate of change for the given pulse counter."""
        if self._sensor.pulses_per_second is None:
            return None

        result = (
            self._sensor.pulses_per_second
            * self._counted_quantity_per_pulse
            * self._seconds_per_time_unit
        )
        return result

    @property
    def _seconds_per_time_unit(self) -> int:
        """Return the number of seconds in the given display time unit."""
        if self._time_unit == TIME_SECONDS:
            return 1
        if self._time_unit == TIME_MINUTES:
            return 60
        if self._time_unit == TIME_HOURS:
            return 3600

        # Config schema should have ensured it is one of the above values
        raise Exception(
            f"Invalid value for time unit: {self._time_unit}. Expected one of {TIME_SECONDS}, {TIME_MINUTES}, or {TIME_HOURS}"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return total pulses in the data dictionary."""
        return {DATA_PULSES: self._sensor.pulses}


class TemperatureSensor(GEMSensor):
    """Entity showing temperature from one temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(
        self, monitor: greeneye.monitor.Monitor, number: int, name: str, unit: str
    ) -> None:
        """Construct the entity."""
        super().__init__(
            monitor, name, "temp", monitor.temperature_sensors[number - 1], number
        )
        self._sensor: greeneye.monitor.TemperatureSensor = self._sensor
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | None:
        """Return the current temperature being reported by this sensor."""
        return self._sensor.temperature


class VoltageSensor(GEMSensor):
    """Entity showing voltage."""

    _attr_native_unit_of_measurement = ELECTRIC_POTENTIAL_VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE

    def __init__(
        self, monitor: greeneye.monitor.Monitor, number: int, name: str
    ) -> None:
        """Construct the entity."""
        super().__init__(monitor, name, "volts", monitor.voltage_sensor, number)
        self._sensor: greeneye.monitor.VoltageSensor = self._sensor

    @property
    def native_value(self) -> float | None:
        """Return the current voltage being reported by this sensor."""
        return self._sensor.voltage
