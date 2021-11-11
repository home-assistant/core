"""Tests for greeneye_monitor sensors."""
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.greeneye_monitor.sensor import (
    DATA_PULSES,
    DATA_WATT_SECONDS,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as get_entity_registry

from .common import (
    SINGLE_MONITOR_CONFIG_POWER_SENSORS,
    SINGLE_MONITOR_CONFIG_PULSE_COUNTERS,
    SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS,
    SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS,
    SINGLE_MONITOR_SERIAL_NUMBER,
    mock_monitor,
    setup_greeneye_monitor_component_with_config,
)
from .conftest import assert_sensor_state


async def test_disable_sensor_before_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor disabled before its monitor connected stops listening for new monitors."""
    # The sensor base class handles connecting the monitor, so we test this with a single voltage sensor for ease
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )

    assert len(monitors.listeners) == 1
    await disable_entity(hass, "sensor.voltage_1")
    assert len(monitors.listeners) == 0  # Make sure we cleaned up the listener


async def test_updates_state_when_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor updates its state when its monitor first connects."""
    # The sensor base class handles updating the state on connection, so we test this with a single voltage sensor for ease
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )

    assert_sensor_state(hass, "sensor.voltage_1", STATE_UNKNOWN)
    assert len(monitors.listeners) == 1
    connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert len(monitors.listeners) == 0  # Make sure we cleaned up the listener
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")


async def test_disable_sensor_after_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor disabled after its monitor connected stops listening for sensor changes."""
    # The sensor base class handles connecting the monitor, so we test this with a single voltage sensor for ease
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )
    monitor = connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)

    assert len(monitor.listeners) == 1
    await disable_entity(hass, "sensor.voltage_1")
    assert len(monitor.listeners) == 0


async def test_updates_state_when_sensor_pushes(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor entity updates its state when the underlying sensor pushes an update."""
    # The sensor base class handles triggering state updates, so we test this with a single voltage sensor for ease
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )
    monitor = connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")

    monitor.voltage = 119.8
    monitor.notify_all_listeners()
    assert_sensor_state(hass, "sensor.voltage_1", "119.8")


async def test_power_sensor_initially_unknown(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that the power sensor can handle its initial state being unknown (since the GEM API needs at least two packets to arrive before it can compute watts)."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_POWER_SENSORS
    )
    connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert_sensor_state(
        hass, "sensor.channel_1", STATE_UNKNOWN, {DATA_WATT_SECONDS: 1000}
    )
    # This sensor was configured with net metering on, so we should be taking the
    # polarized value
    assert_sensor_state(
        hass, "sensor.channel_two", STATE_UNKNOWN, {DATA_WATT_SECONDS: -400}
    )


async def test_power_sensor(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a power sensor reports its values correctly, including handling net metering."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_POWER_SENSORS
    )
    monitor = connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    monitor.channels[0].watts = 120.0
    monitor.channels[1].watts = 120.0
    monitor.channels[0].notify_all_listeners()
    monitor.channels[1].notify_all_listeners()
    assert_sensor_state(hass, "sensor.channel_1", "120.0", {DATA_WATT_SECONDS: 1000})
    # This sensor was configured with net metering on, so we should be taking the
    # polarized value
    assert_sensor_state(hass, "sensor.channel_two", "120.0", {DATA_WATT_SECONDS: -400})


async def test_pulse_counter(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a pulse counter sensor reports its values properly, including calculating different units."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_PULSE_COUNTERS
    )
    connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert_sensor_state(hass, "sensor.pulse_a", "10.0", {DATA_PULSES: 1000})
    # This counter was configured with each pulse meaning 0.5 gallons and
    # wanting to show gallons per minute, so 10 pulses per second -> 300 gal/min
    assert_sensor_state(hass, "sensor.pulse_2", "300.0", {DATA_PULSES: 1000})
    # This counter was configured with each pulse meaning 0.5 gallons and
    # wanting to show gallons per hour, so 10 pulses per second -> 18000 gal/hr
    assert_sensor_state(hass, "sensor.pulse_3", "18000.0", {DATA_PULSES: 1000})


async def test_temperature_sensor(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a temperature sensor reports its values properly, including proper handling of when its native unit is different from that configured in hass."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS
    )
    connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    # The config says that the sensor is reporting in Fahrenheit; if we set that up
    # properly, HA will have converted that to Celsius by default.
    assert_sensor_state(hass, "sensor.temp_a", "0.0")


async def test_voltage_sensor(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a voltage sensor reports its values properly."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )
    connect_monitor(monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")


def connect_monitor(monitors: AsyncMock, serial_number: int) -> MagicMock:
    """Simulate a monitor connecting to Home Assistant. Returns the mock monitor API object."""
    monitor = mock_monitor(serial_number)
    monitors.add_monitor(monitor)
    return monitor


async def disable_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Disable the given entity."""
    entity_registry = get_entity_registry(hass)
    entity_registry.async_update_entity(entity_id, disabled_by="user")
    await hass.async_block_till_done()
