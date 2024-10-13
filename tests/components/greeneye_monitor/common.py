"""Common helpers for greeneye_monitor tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.greeneye_monitor import (
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
    DOMAIN,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_TEMPERATURE_UNIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

SINGLE_MONITOR_SERIAL_NUMBER = 110011


def make_single_monitor_config_with_sensors(sensors: dict[str, Any]) -> dict[str, Any]:
    """Wrap the given sensor config in the boilerplate for a single monitor with serial number SINGLE_MONITOR_SERIAL_NUMBER."""
    return {
        DOMAIN: {
            CONF_PORT: 7513,
            CONF_MONITORS: [
                {
                    CONF_SERIAL_NUMBER: f"00{SINGLE_MONITOR_SERIAL_NUMBER}",
                    **sensors,
                }
            ],
        }
    }


SINGLE_MONITOR_CONFIG_NO_SENSORS = make_single_monitor_config_with_sensors({})
SINGLE_MONITOR_CONFIG_PULSE_COUNTERS = make_single_monitor_config_with_sensors(
    {
        CONF_PULSE_COUNTERS: [
            {
                CONF_NUMBER: 1,
                CONF_NAME: "pulse_a",
                CONF_COUNTED_QUANTITY: "pulses",
                CONF_COUNTED_QUANTITY_PER_PULSE: 1.0,
                CONF_TIME_UNIT: "s",
            },
            {
                CONF_NUMBER: 2,
                CONF_NAME: "pulse_2",
                CONF_COUNTED_QUANTITY: "gal",
                CONF_COUNTED_QUANTITY_PER_PULSE: 0.5,
                CONF_TIME_UNIT: "min",
            },
            {
                CONF_NUMBER: 3,
                CONF_NAME: "pulse_3",
                CONF_COUNTED_QUANTITY: "gal",
                CONF_COUNTED_QUANTITY_PER_PULSE: 0.5,
                CONF_TIME_UNIT: "h",
            },
            {
                CONF_NUMBER: 4,
                CONF_NAME: "pulse_d",
                CONF_COUNTED_QUANTITY: "pulses",
                CONF_COUNTED_QUANTITY_PER_PULSE: 1.0,
                CONF_TIME_UNIT: "s",
            },
        ]
    }
)

SINGLE_MONITOR_CONFIG_POWER_SENSORS = make_single_monitor_config_with_sensors(
    {
        CONF_CHANNELS: [
            {
                CONF_NUMBER: 1,
                CONF_NAME: "channel 1",
            },
            {
                CONF_NUMBER: 2,
                CONF_NAME: "channel two",
                CONF_NET_METERING: True,
            },
        ]
    }
)


SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS = make_single_monitor_config_with_sensors(
    {
        CONF_TEMPERATURE_SENSORS: {
            CONF_TEMPERATURE_UNIT: "F",
            CONF_SENSORS: [
                {CONF_NUMBER: 1, CONF_NAME: "temp_a"},
                {CONF_NUMBER: 2, CONF_NAME: "temp_2"},
                {CONF_NUMBER: 3, CONF_NAME: "temp_c"},
                {CONF_NUMBER: 4, CONF_NAME: "temp_d"},
                {CONF_NUMBER: 5, CONF_NAME: "temp_5"},
                {CONF_NUMBER: 6, CONF_NAME: "temp_f"},
                {CONF_NUMBER: 7, CONF_NAME: "temp_g"},
                {CONF_NUMBER: 8, CONF_NAME: "temp_h"},
            ],
        }
    }
)

SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS = make_single_monitor_config_with_sensors(
    {
        CONF_VOLTAGE_SENSORS: [
            {
                CONF_NUMBER: 1,
                CONF_NAME: "voltage 1",
            },
        ]
    }
)

MULTI_MONITOR_CONFIG = {
    DOMAIN: {
        CONF_PORT: 7513,
        CONF_MONITORS: [
            {
                CONF_SERIAL_NUMBER: "00000001",
                CONF_TEMPERATURE_SENSORS: {
                    CONF_TEMPERATURE_UNIT: "C",
                    CONF_SENSORS: [{CONF_NUMBER: 1, CONF_NAME: "unit_1_temp_1"}],
                },
            },
            {
                CONF_SERIAL_NUMBER: "00000002",
                CONF_TEMPERATURE_SENSORS: {
                    CONF_TEMPERATURE_UNIT: "F",
                    CONF_SENSORS: [{CONF_NUMBER: 1, CONF_NAME: "unit_2_temp_1"}],
                },
            },
            {
                CONF_SERIAL_NUMBER: "00000003",
                CONF_TEMPERATURE_SENSORS: {
                    CONF_TEMPERATURE_UNIT: "C",
                    CONF_SENSORS: [{CONF_NUMBER: 1, CONF_NAME: "unit_3_temp_1"}],
                },
            },
        ],
    }
}


async def setup_greeneye_monitor_component_with_config(
    hass: HomeAssistant, config: ConfigType
) -> bool:
    """Set up the greeneye_monitor component with the given config. Return True if successful, False otherwise."""
    result = await async_setup_component(
        hass,
        DOMAIN,
        config,
    )
    await hass.async_block_till_done()

    return result


def mock_with_listeners() -> MagicMock:
    """Create a MagicMock with methods that follow the same pattern for working with listeners in the greeneye_monitor API."""
    mock = MagicMock()
    add_listeners(mock)
    return mock


def async_mock_with_listeners() -> AsyncMock:
    """Create an AsyncMock with methods that follow the same pattern for working with listeners in the greeneye_monitor API."""
    mock = AsyncMock()
    add_listeners(mock)
    return mock


def add_listeners(mock: MagicMock | AsyncMock) -> None:
    """Add add_listener and remove_listener methods to the given mock that behave like their counterparts on objects from the greeneye_monitor API, plus a notify_all_listeners method that calls all registered listeners."""
    mock.listeners = []
    mock.add_listener = mock.listeners.append
    mock.remove_listener = mock.listeners.remove

    def notify_all_listeners(*args):
        for listener in list(mock.listeners):
            listener(*args)

    mock.notify_all_listeners = notify_all_listeners


def mock_pulse_counter() -> MagicMock:
    """Create a mock GreenEye Monitor pulse counter."""
    pulse_counter = mock_with_listeners()
    pulse_counter.pulses = 1000
    pulse_counter.pulses_per_second = 10
    return pulse_counter


def mock_temperature_sensor() -> MagicMock:
    """Create a mock GreenEye Monitor temperature sensor."""
    temperature_sensor = mock_with_listeners()
    temperature_sensor.temperature = 32.0
    return temperature_sensor


def mock_voltage_sensor() -> MagicMock:
    """Create a mock GreenEye Monitor voltage sensor."""
    voltage_sensor = mock_with_listeners()
    voltage_sensor.voltage = 120.0
    return voltage_sensor


def mock_channel() -> MagicMock:
    """Create a mock GreenEye Monitor CT channel."""
    channel = mock_with_listeners()
    channel.absolute_watt_seconds = 1000
    channel.polarized_watt_seconds = -400
    channel.watts = None
    return channel


def mock_monitor(serial_number: int) -> MagicMock:
    """Create a mock GreenEye Monitor."""
    monitor = mock_with_listeners()
    monitor.serial_number = serial_number
    monitor.voltage_sensor = mock_voltage_sensor()
    monitor.pulse_counters = [mock_pulse_counter() for i in range(4)]
    monitor.temperature_sensors = [mock_temperature_sensor() for i in range(8)]
    monitor.channels = [mock_channel() for i in range(32)]
    return monitor


async def connect_monitor(
    hass: HomeAssistant, monitors: AsyncMock, serial_number: int
) -> MagicMock:
    """Simulate a monitor connecting to Home Assistant. Returns the mock monitor API object."""
    monitor = mock_monitor(serial_number)
    monitors.add_monitor(monitor)
    await hass.async_block_till_done()
    return monitor
