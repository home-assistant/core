"""Tests for greeneye_monitor sensors."""

from unittest.mock import AsyncMock

from homeassistant.components.greeneye_monitor.sensor import (
    DATA_PULSES,
    DATA_WATT_SECONDS,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    RegistryEntryDisabler,
    async_get as get_entity_registry,
)

from .common import (
    MULTI_MONITOR_CONFIG,
    SINGLE_MONITOR_CONFIG_POWER_SENSORS,
    SINGLE_MONITOR_CONFIG_PULSE_COUNTERS,
    SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS,
    SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS,
    SINGLE_MONITOR_SERIAL_NUMBER,
    connect_monitor,
    setup_greeneye_monitor_component_with_config,
)
from .conftest import assert_sensor_state


async def test_sensor_does_not_exist_before_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor does not exist before its monitor is connected."""
    # The sensor base class handles connecting the monitor, so we test this with a single voltage sensor for ease
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )

    entity_registry = get_entity_registry(hass)
    assert entity_registry.async_get("sensor.voltage_1") is None


async def test_sensors_created_when_monitor_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that sensors get created when the monitor first connects."""
    # The sensor base class handles updating the state on connection, so we test this with a single voltage sensor for ease
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )

    assert len(monitors.listeners) == 1
    await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert len(monitors.listeners) == 0  # Make sure we cleaned up the listener
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")


async def test_sensors_created_during_setup_if_monitor_already_connected(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that sensors get created during setup if the monitor happens to connect really quickly."""
    # The sensor base class handles updating the state on connection, so we test this with a single voltage sensor for ease
    await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )

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
    monitor = await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)

    assert len(monitor.voltage_sensor.listeners) == 1
    await disable_entity(hass, "sensor.voltage_1")
    assert len(monitor.voltage_sensor.listeners) == 0


async def test_updates_state_when_sensor_pushes(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that a sensor entity updates its state when the underlying sensor pushes an update."""
    # The sensor base class handles triggering state updates, so we test this with a single voltage sensor for ease
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )
    monitor = await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")

    monitor.voltage_sensor.voltage = 119.8
    monitor.voltage_sensor.notify_all_listeners()
    assert_sensor_state(hass, "sensor.voltage_1", "119.8")


async def test_power_sensor_initially_unknown(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that the power sensor can handle its initial state being unknown (since the GEM API needs at least two packets to arrive before it can compute watts)."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_POWER_SENSORS
    )
    await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
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
    monitor = await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    monitor.channels[0].watts = 120.0
    monitor.channels[1].watts = 120.0
    monitor.channels[0].notify_all_listeners()
    monitor.channels[1].notify_all_listeners()
    assert_sensor_state(hass, "sensor.channel_1", "120.0", {DATA_WATT_SECONDS: 1000})
    # This sensor was configured with net metering on, so we should be taking the
    # polarized value
    assert_sensor_state(hass, "sensor.channel_two", "120.0", {DATA_WATT_SECONDS: -400})


async def test_pulse_counter_initially_unknown(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that the pulse counter sensor can handle its initial state being unknown (since the GEM API needs at least two packets to arrive before it can compute pulses per time)."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_PULSE_COUNTERS
    )
    monitor = await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    monitor.pulse_counters[0].pulses_per_second = None
    monitor.pulse_counters[1].pulses_per_second = None
    monitor.pulse_counters[2].pulses_per_second = None
    monitor.pulse_counters[0].notify_all_listeners()
    monitor.pulse_counters[1].notify_all_listeners()
    monitor.pulse_counters[2].notify_all_listeners()
    assert_sensor_state(hass, "sensor.pulse_a", STATE_UNKNOWN, {DATA_PULSES: 1000})
    # This counter was configured with each pulse meaning 0.5 gallons and
    # wanting to show gallons per minute, so 10 pulses per second -> 300 gal/min
    assert_sensor_state(hass, "sensor.pulse_2", STATE_UNKNOWN, {DATA_PULSES: 1000})
    # This counter was configured with each pulse meaning 0.5 gallons and
    # wanting to show gallons per hour, so 10 pulses per second -> 18000 gal/hr
    assert_sensor_state(hass, "sensor.pulse_3", STATE_UNKNOWN, {DATA_PULSES: 1000})


async def test_pulse_counter(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a pulse counter sensor reports its values properly, including calculating different units."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_PULSE_COUNTERS
    )
    await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
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
    await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    # The config says that the sensor is reporting in Fahrenheit; if we set that up
    # properly, HA will have converted that to Celsius by default.
    assert_sensor_state(hass, "sensor.temp_a", "0.0")


async def test_voltage_sensor(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that a voltage sensor reports its values properly."""
    await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )
    await connect_monitor(hass, monitors, SINGLE_MONITOR_SERIAL_NUMBER)
    assert_sensor_state(hass, "sensor.voltage_1", "120.0")


async def test_multi_monitor_sensors(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that sensors still work when multiple monitors are registered."""
    await setup_greeneye_monitor_component_with_config(hass, MULTI_MONITOR_CONFIG)
    await connect_monitor(hass, monitors, 1)
    await connect_monitor(hass, monitors, 2)
    await connect_monitor(hass, monitors, 3)
    assert_sensor_state(hass, "sensor.unit_1_temp_1", "32.0")
    assert_sensor_state(hass, "sensor.unit_2_temp_1", "0.0")
    assert_sensor_state(hass, "sensor.unit_3_temp_1", "32.0")


async def disable_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Disable the given entity."""
    entity_registry = get_entity_registry(hass)
    entity_registry.async_update_entity(
        entity_id, disabled_by=RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
