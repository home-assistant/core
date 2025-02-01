"""Common fixtures for testing greeneye_monitor."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.greeneye_monitor import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfElectricPotential, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import add_listeners


def assert_sensor_state(
    hass: HomeAssistant,
    entity_id: str,
    expected_state: str,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Assert that the given entity has the expected state and at least the provided attributes."""
    state = hass.states.get(entity_id)
    assert state
    actual_state = state.state
    assert actual_state == expected_state
    if not attributes:
        return
    for key, value in attributes.items():
        assert key in state.attributes
        assert state.attributes[key] == value


def assert_temperature_sensor_registered(
    hass: HomeAssistant,
    serial_number: int,
    number: int,
    name: str,
):
    """Assert that a temperature sensor entity was registered properly."""
    sensor = assert_sensor_registered(hass, serial_number, "temp", number, name)
    assert sensor.original_device_class is SensorDeviceClass.TEMPERATURE


def assert_pulse_counter_registered(
    hass: HomeAssistant,
    serial_number: int,
    number: int,
    name: str,
    quantity: str,
    per_time: str,
):
    """Assert that a pulse counter entity was registered properly."""
    sensor = assert_sensor_registered(hass, serial_number, "pulse", number, name)
    assert sensor.unit_of_measurement == f"{quantity}/{per_time}"


def assert_power_sensor_registered(
    hass: HomeAssistant, serial_number: int, number: int, name: str
) -> None:
    """Assert that a power sensor entity was registered properly."""
    sensor = assert_sensor_registered(hass, serial_number, "current", number, name)
    assert sensor.unit_of_measurement == UnitOfPower.WATT
    assert sensor.original_device_class is SensorDeviceClass.POWER


def assert_voltage_sensor_registered(
    hass: HomeAssistant, serial_number: int, number: int, name: str
) -> None:
    """Assert that a voltage sensor entity was registered properly."""
    sensor = assert_sensor_registered(hass, serial_number, "volts", number, name)
    assert sensor.unit_of_measurement == UnitOfElectricPotential.VOLT
    assert sensor.original_device_class is SensorDeviceClass.VOLTAGE


def assert_sensor_registered(
    hass: HomeAssistant,
    serial_number: int,
    sensor_type: str,
    number: int,
    name: str,
) -> er.RegistryEntry:
    """Assert that a sensor entity of a given type was registered properly."""
    entity_registry = er.async_get(hass)
    unique_id = f"{serial_number}-{sensor_type}-{number}"

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    sensor = entity_registry.async_get(entity_id)
    assert sensor
    assert sensor.unique_id == unique_id
    assert sensor.original_name == name

    return sensor


@pytest.fixture
def monitors() -> Generator[AsyncMock]:
    """Provide a mock greeneye.Monitors object that has listeners and can add new monitors."""
    with patch("greeneye.Monitors", autospec=True) as mock_monitors:
        mock = mock_monitors.return_value
        add_listeners(mock)
        mock.monitors = {}

        def add_monitor(monitor: MagicMock) -> None:
            """Add the given mock monitor as a monitor with the given serial number, notifying any listeners on the Monitors object."""
            serial_number = monitor.serial_number
            mock.monitors[serial_number] = monitor
            mock.notify_all_listeners(monitor)

        mock.add_monitor = add_monitor
        yield mock
