"""Support for the sensors in a GreenEye Monitor."""

from __future__ import annotations

from typing import Any

import greeneye

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_SENSORS,
    CONF_TEMPERATURE_UNIT,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
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
            channel_configs = monitor_config[CONF_CHANNELS]
            entities: list[GEMSensor] = [
                CurrentSensor(
                    monitor,
                    sensor[CONF_NUMBER],
                    sensor[CONF_NAME],
                    sensor[CONF_NET_METERING],
                )
                for sensor in channel_configs
            ]

            pulse_counter_configs = monitor_config[CONF_PULSE_COUNTERS]
            entities.extend(
                PulseCounter(
                    monitor,
                    sensor[CONF_NUMBER],
                    sensor[CONF_NAME],
                    sensor[CONF_COUNTED_QUANTITY],
                    sensor[CONF_TIME_UNIT],
                    sensor[CONF_COUNTED_QUANTITY_PER_PULSE],
                )
                for sensor in pulse_counter_configs
            )

            temperature_sensor_configs = monitor_config[CONF_TEMPERATURE_SENSORS]
            entities.extend(
                TemperatureSensor(
                    monitor,
                    sensor[CONF_NUMBER],
                    sensor[CONF_NAME],
                    temperature_sensor_configs[CONF_TEMPERATURE_UNIT],
                )
                for sensor in temperature_sensor_configs[CONF_SENSORS]
            )

            voltage_sensor_configs = monitor_config[CONF_VOLTAGE_SENSORS]
            entities.extend(
                VoltageSensor(monitor, sensor[CONF_NUMBER], sensor[CONF_NAME])
                for sensor in voltage_sensor_configs
            )

            async_add_entities(entities)
            monitor_configs.remove(monitor_config)

        if len(monitor_configs) == 0:
            monitors.remove_listener(on_new_monitor)

    monitors: greeneye.Monitors = hass.data[DATA_GREENEYE_MONITOR]
    monitors.add_listener(on_new_monitor)
    for monitor in monitors.monitors.values():
        on_new_monitor(monitor)


UnderlyingSensorType = (
    greeneye.monitor.Channel
    | greeneye.monitor.PulseCounter
    | greeneye.monitor.TemperatureSensor
    | greeneye.monitor.VoltageSensor
)


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

    _attr_native_unit_of_measurement = UnitOfPower.WATT
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

        return (
            self._sensor.pulses_per_second
            * self._counted_quantity_per_pulse
            * self._seconds_per_time_unit
        )

    @property
    def _seconds_per_time_unit(self) -> int:
        """Return the number of seconds in the given display time unit."""
        if self._time_unit == UnitOfTime.SECONDS:
            return 1
        if self._time_unit == UnitOfTime.MINUTES:
            return 60
        if self._time_unit == UnitOfTime.HOURS:
            return 3600

        # Config schema should have ensured it is one of the above values
        raise RuntimeError(
            f"Invalid value for time unit: {self._time_unit}. Expected one of"
            f" {UnitOfTime.SECONDS}, {UnitOfTime.MINUTES}, or {UnitOfTime.HOURS}"
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

    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
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
