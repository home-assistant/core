"""Tests for greeneye_monitor sensors."""
from unittest.mock import AsyncMock

from homeassistant.components.greeneye_monitor.sensor import (
    DATA_PULSES,
    DATA_WATT_SECONDS,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.helpers.typing import ConfigType

from .common import (
    SINGLE_MONITOR_CONFIG_POWER_SENSORS,
    SINGLE_MONITOR_CONFIG_PULSE_COUNTERS,
    SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS,
    SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS,
    SINGLE_MONITOR_SERIAL_NUMBER,
    mock_with_listeners,
    setup_greeneye_monitor_component_with_config,
)
from .conftest import assert_sensor_state


async def test_disable_sensor_before_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor disabled before its monitor connected stops listening for new monitors."""
    # The sensor base class handles connecting the monitor, so we test this with a single voltage sensor for ease
    await setup_monitor(hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS)

    assert len(monitors.listeners) == 1
    await disable_entity(hass, "sensor.voltage_1")
    assert len(monitors.listeners) == 0  # Make sure we cleaned up the listener


async def test_updates_state_when_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor updates its state when its monitor first connects."""
    # The sensor base class handles updating the state on connection, so we test this with a single voltage sensor for ease
    monitor = await setup_monitor(hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS)

    assert_sensor_state(hass, "sensor.voltage_1", STATE_UNKNOWN)
    monitor.voltage = 120.0
    assert len(monitors.listeners) == 1
    monitors.add_monitor(SINGLE_MONITOR_SERIAL_NUMBER, monitor)
    assert len(monitors.listeners) == 0  # Make sure we cleaned up the listener
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")


async def test_disable_sensor_after_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor disabled after its monitor connected stops listening for sensor changes."""
    # The sensor base class handles connecting the monitor, so we test this with a single voltage sensor for ease
    monitor = await setup_monitor(hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS)
    monitor.voltage = 120.0
    monitors.add_monitor(SINGLE_MONITOR_SERIAL_NUMBER, monitor)

    assert len(monitor.listeners) == 1
    await disable_entity(hass, "sensor.voltage_1")
    assert len(monitor.listeners) == 0


async def test_updates_state_when_sensor_pushes(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor entity updates its state when the underlying sensor pushes an update."""
    # The sensor base class handles triggering state updates, so we test this with a single voltage sensor for ease
    monitor = await setup_monitor(hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS)
    monitor.voltage = 120.0
    monitors.add_monitor(SINGLE_MONITOR_SERIAL_NUMBER, monitor)
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")

    monitor.voltage = 119.8
    monitor.notify_all_listeners()
    assert_sensor_state(hass, "sensor.voltage_1", "119.8")


async def test_power_sensor(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a power sensor reports its values correctly, including handling net metering."""
    monitor = await setup_monitor(hass, SINGLE_MONITOR_CONFIG_POWER_SENSORS)
    channel = mock_with_listeners()
    channel.watts = 120.0
    channel.absolute_watt_seconds = 1000
    channel.polarized_watt_seconds = -400
    monitor.channels = [channel, channel] + [None] * 30
    monitors.add_monitor(SINGLE_MONITOR_SERIAL_NUMBER, monitor)
    assert_sensor_state(hass, "sensor.channel_1", "120.0", {DATA_WATT_SECONDS: 1000})
    # This sensor was configured with net metering on, so we should be taking the
    # polarized value
    assert_sensor_state(hass, "sensor.channel_two", "120.0", {DATA_WATT_SECONDS: -400})


async def test_pulse_counter(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a pulse counter sensor reports its values properly, including calculating different units."""
    monitor = await setup_monitor(hass, SINGLE_MONITOR_CONFIG_PULSE_COUNTERS)
    pulse_counter = mock_with_listeners()
    pulse_counter.pulses = 1000
    pulse_counter.pulses_per_second = 10
    monitor.pulse_counters = [pulse_counter] * 4
    monitors.add_monitor(SINGLE_MONITOR_SERIAL_NUMBER, monitor)
    assert_sensor_state(hass, "sensor.pulse_a", "10.0", {DATA_PULSES: 1000})
    # This counter was configured with each pulse meaning 0.5 gallons and
    # wanting to show gallons per minute, so 10 pulses per second -> 300 gal/min
    assert_sensor_state(hass, "sensor.pulse_2", "300.0", {DATA_PULSES: 1000})
    # This counter was configured with each pulse meaning 0.5 gallons and
    # wanting to show gallons per hour, so 10 pulses per second -> 18000 gal/hr
    assert_sensor_state(hass, "sensor.pulse_3", "18000.0", {DATA_PULSES: 1000})


async def test_temperature_sensor(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a temperature sensor reports its values properly, including proper handling of when its native unit is different from that configured in hass."""
    monitor = await setup_monitor(hass, SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS)
    temperature_sensor = mock_with_listeners()
    temperature_sensor.temperature = 32.0
    monitor.temperature_sensors = [temperature_sensor] * 8
    monitors.add_monitor(SINGLE_MONITOR_SERIAL_NUMBER, monitor)
    # The config says that the sensor is reporting in Fahrenheit; if we set that up
    # properly, HA will have converted that to Celsius by default.
    assert_sensor_state(hass, "sensor.temp_a", "0.0")


async def test_voltage_sensor(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a voltage sensor reports its values properly."""
    monitor = await setup_monitor(hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS)
    monitor.voltage = 120.0
    monitors.add_monitor(SINGLE_MONITOR_SERIAL_NUMBER, monitor)
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")


async def setup_monitor(hass: HomeAssistant, config: ConfigType) -> AsyncMock:
    """Set up the component for a single monitor and return a mock monitor."""
    monitor = mock_with_listeners()
    await setup_greeneye_monitor_component_with_config(hass, config)
    return monitor


async def disable_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Disable the given entity."""
    entity_registry = get_entity_registry(hass)
    entity_registry.async_update_entity(entity_id, disabled_by="user")
    await hass.async_block_till_done()
