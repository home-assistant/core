"""Test the ThermoPro config flow."""

from unittest.mock import patch

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.components.thermopro.const import DOMAIN
from homeassistant.components.thermopro.coordinator import (
    ThermoProBluetoothProcessorCoordinator,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import TP357_SERVICE_INFO, TP962R_SERVICE_INFO, TP962R_SERVICE_INFO_2

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors_tp962r(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, TP962R_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_2_internal_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "25"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 2 Internal Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_2_ambient_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "25"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 2 Ambient Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp962r_0000_probe_2_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "100"
    assert (
        battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP962R (0000) Probe 2 Battery"
    )
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    inject_bluetooth_service_info(hass, TP962R_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 6

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_1_internal_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "37"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 1 Internal Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.tp962r_0000_probe_1_ambient_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "37"
    assert (
        temp_sensor_attributes[ATTR_FRIENDLY_NAME]
        == "TP962R (0000) Probe 1 Ambient Temperature"
    )
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp962r_0000_probe_1_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "82.0"
    assert (
        battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP962R (0000) Probe 1 Battery"
    )
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    temp_sensor = hass.states.get("sensor.tp357_2142_temperature")
    temp_sensor_attributes = temp_sensor.attributes
    assert temp_sensor.state == "24.1"
    assert temp_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP357 (2142) Temperature"
    assert temp_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    battery_sensor = hass.states.get("sensor.tp357_2142_battery")
    battery_sensor_attributes = battery_sensor.attributes
    assert battery_sensor.state == "100"
    assert battery_sensor_attributes[ATTR_FRIENDLY_NAME] == "TP357 (2142) Battery"
    assert battery_sensor_attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert battery_sensor_attributes[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_restore_last_known_state(hass: HomeAssistant) -> None:
    """Test sensors restore last known data when available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    temp_sensor = hass.states.get("sensor.tp357_2142_temperature")
    assert temp_sensor is not None
    assert temp_sensor.state == "24.1"

    battery_sensor = hass.states.get("sensor.tp357_2142_battery")
    assert battery_sensor is not None
    assert battery_sensor.state == "100"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_triggers_rediscovery_on_unavailable(hass: HomeAssistant) -> None:
    """Ensure rediscovery triggers when device goes unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: ThermoProBluetoothProcessorCoordinator = entry.runtime_data
    with patch(
        "homeassistant.components.thermopro.coordinator.bluetooth.async_rediscover_address"
    ) as mock_rediscover:
        coordinator._async_handle_unavailable(TP357_SERVICE_INFO)  # noqa: SLF001
        coordinator._async_handle_unavailable(TP357_SERVICE_INFO)  # noqa: SLF001
    mock_rediscover.assert_called_once()

    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.thermopro.coordinator.bluetooth.async_rediscover_address"
    ) as mock_rediscover_again:
        coordinator._async_handle_unavailable(TP357_SERVICE_INFO)  # noqa: SLF001
    mock_rediscover_again.assert_called_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_restore_and_update(hass: HomeAssistant) -> None:
    """Test entities are created on first broadcast and update with new data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Initially no entities - device hasn't been seen
    assert len(hass.states.async_all()) == 0

    # Device broadcasts and entities are created
    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3

    # Verify entities have data
    temp_sensor = hass.states.get("sensor.tp357_2142_temperature")
    assert temp_sensor is not None
    assert temp_sensor.state == "24.1"

    battery_sensor = hass.states.get("sensor.tp357_2142_battery")
    assert battery_sensor is not None
    assert battery_sensor.state == "100"

    # Verify coordinator is available and properly configured for data restoration
    coordinator = entry.runtime_data
    assert isinstance(coordinator, ThermoProBluetoothProcessorCoordinator)
    assert coordinator.available
    # The coordinator should have a restore_key (config entry ID) for data persistence
    assert coordinator.restore_key == entry.entry_id

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
