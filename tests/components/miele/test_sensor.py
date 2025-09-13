"""Tests for miele sensor module."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pymiele import MieleDevices
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test sensor state after polling the API for data."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states_api_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
    push_data_and_actions: None,
) -> None:
    """Test sensor state when the API pushes data via SSE."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["hob.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hob_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["fridge_freezer.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fridge_freezer_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_oven_temperatures_scenario(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    mock_config_entry: MockConfigEntry,
    device_fixture: MieleDevices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Parametrized test for verifying temperature sensors for oven devices."""

    # Initial state when the oven is and created for the first time - don't know if it supports core temperature (probe)
    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 0)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 0)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 0)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 0)

    # Simulate temperature settings, no probe temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = 8000
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        80.0
    )
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = 2150
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = 21.5

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "21.5", 1)
    check_sensor_state(hass, "sensor.oven_target_temperature", "80.0", 1)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 1)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 1)

    # Simulate unsetting temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        None
    )
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = None

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 2)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 2)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 2)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 2)

    # Simulate temperature settings with probe temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = 8000
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        80.0
    )
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0]["value_raw"] = 3000
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0][
        "value_localized"
    ] = 30.0
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = 2183
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = 21.83
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_raw"] = 2200
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_localized"] = 22.0

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "21.83", 3)
    check_sensor_state(hass, "sensor.oven_target_temperature", "80.0", 3)
    check_sensor_state(hass, "sensor.oven_core_temperature", "22.0", 2)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", "30.0", 3)

    # Simulate unsetting temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        None
    )
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0][
        "value_raw"
    ] = -32768
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0][
        "value_localized"
    ] = None
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = None
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_localized"] = None

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 4)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 4)
    check_sensor_state(hass, "sensor.oven_core_temperature", "unknown", 4)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", "unknown", 4)


def check_sensor_state(
    hass: HomeAssistant,
    sensor_entity: str,
    expected: str,
    step: int,
):
    """Check the state of sensor matches the expected state."""

    state = hass.states.get(sensor_entity)

    if expected is None:
        assert state is None, (
            f"[{sensor_entity}] Step {step + 1}: got {state.state}, expected nothing"
        )
    else:
        assert state is not None, f"Missing entity: {sensor_entity}"
        assert state.state == expected, (
            f"[{sensor_entity}] Step {step + 1}: got {state.state}, expected {expected}"
        )


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_temperature_sensor_registry_lookup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_miele_client: MagicMock,
    setup_platform: None,
    device_fixture: MieleDevices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that core temperature sensor is provided by the integration after looking up in entity registry."""

    # Initial state, the oven is showing core temperature (probe)
    freezer.tick(timedelta(seconds=130))
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_raw"] = 2200
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_localized"] = 22.0
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = "sensor.oven_core_temperature"

    assert hass.states.get(entity_id) is not None
    assert hass.states.get(entity_id).state == "22.0"

    # reload device when turned off, reporting the invalid value
    mock_miele_client.get_devices.return_value = await async_load_json_object_fixture(
        hass, "oven.json", DOMAIN
    )

    # unload config entry and reload to make sure that the entity is still provided
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unknown"


@pytest.mark.parametrize("load_device_file", ["vacuum_device.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_vacuum_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test robot vacuum cleaner sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["fan_devices.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fan_hob_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test robot fan / hob sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["coffee_system.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coffee_system_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test coffee system sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["laundry.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_laundry_wash_scenario(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    mock_config_entry: MockConfigEntry,
    device_fixture: MieleDevices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Parametrized test for verifying time sensors for wahsing machine devices when API glitches at program end."""

    step = 0

    # Initial state when the washing machine is off
    check_sensor_state(hass, "sensor.washing_machine", "off", step)
    check_sensor_state(hass, "sensor.washing_machine_program", "no_program", step)
    check_sensor_state(
        hass, "sensor.washing_machine_program_phase", "not_running", step
    )
    check_sensor_state(
        hass, "sensor.washing_machine_target_temperature", "unknown", step
    )
    check_sensor_state(hass, "sensor.washing_machine_spin_speed", "unknown", step)
    # OFF -> remaining forced to unknown
    check_sensor_state(hass, "sensor.washing_machine_remaining_time", "unknown", step)
    # OFF -> elapsed forced to unknown (some devices continue reporting last value of last cycle)
    check_sensor_state(hass, "sensor.washing_machine_elapsed_time", "unknown", step)
    # consumption sensors have to report "unknown" when the device is not working
    check_sensor_state(
        hass, "sensor.washing_machine_energy_consumption", "unknown", step
    )
    check_sensor_state(
        hass, "sensor.washing_machine_water_consumption", "unknown", step
    )

    # Simulate program started
    device_fixture["DummyWasher"]["state"]["status"]["value_raw"] = 5
    device_fixture["DummyWasher"]["state"]["status"]["value_localized"] = "In use"
    device_fixture["DummyWasher"]["state"]["ProgramID"]["value_raw"] = 3
    device_fixture["DummyWasher"]["state"]["ProgramID"]["value_localized"] = (
        "Minimum iron"
    )
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_raw"] = 260
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_localized"] = (
        "Main wash"
    )
    device_fixture["DummyWasher"]["state"]["remainingTime"][0] = 1
    device_fixture["DummyWasher"]["state"]["remainingTime"][1] = 45
    device_fixture["DummyWasher"]["state"]["targetTemperature"][0]["value_raw"] = 3000
    device_fixture["DummyWasher"]["state"]["targetTemperature"][0][
        "value_localized"
    ] = 30.0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][1] = 12
    device_fixture["DummyWasher"]["state"]["spinningSpeed"]["value_raw"] = 1200
    device_fixture["DummyWasher"]["state"]["spinningSpeed"]["value_localized"] = "1200"
    device_fixture["DummyWasher"]["state"]["ecoFeedback"] = {
        "currentEnergyConsumption": {
            "value": 0.9,
            "unit": "kWh",
        },
        "currentWaterConsumption": {
            "value": 52,
            "unit": "l",
        },
    }

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # at this point, appliance is working, but it started reporting a value from last cycle, so it is forced to 0
    check_sensor_state(hass, "sensor.washing_machine_energy_consumption", "0", step)
    check_sensor_state(hass, "sensor.washing_machine_water_consumption", "0", step)

    # intermediate step, only to report new consumption values
    device_fixture["DummyWasher"]["state"]["ecoFeedback"] = {
        "currentEnergyConsumption": {
            "value": 0.0,
            "unit": "kWh",
        },
        "currentWaterConsumption": {
            "value": 0,
            "unit": "l",
        },
    }

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    step += 1

    check_sensor_state(hass, "sensor.washing_machine", "in_use", step)
    check_sensor_state(hass, "sensor.washing_machine_program", "minimum_iron", step)
    check_sensor_state(hass, "sensor.washing_machine_program_phase", "main_wash", step)
    check_sensor_state(hass, "sensor.washing_machine_target_temperature", "30.0", step)
    check_sensor_state(hass, "sensor.washing_machine_spin_speed", "1200", step)
    # IN_USE -> elapsed, remaining time from API (normal case)
    check_sensor_state(hass, "sensor.washing_machine_remaining_time", "105", step)
    check_sensor_state(hass, "sensor.washing_machine_elapsed_time", "12", step)
    check_sensor_state(hass, "sensor.washing_machine_energy_consumption", "0.0", step)
    check_sensor_state(hass, "sensor.washing_machine_water_consumption", "0", step)

    # intermediate step, only to report new consumption values
    device_fixture["DummyWasher"]["state"]["ecoFeedback"] = {
        "currentEnergyConsumption": {
            "value": 0.1,
            "unit": "kWh",
        },
        "currentWaterConsumption": {
            "value": 7,
            "unit": "l",
        },
    }

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # at this point, it starts reporting value from API
    check_sensor_state(hass, "sensor.washing_machine_energy_consumption", "0.1", step)
    check_sensor_state(hass, "sensor.washing_machine_water_consumption", "7", step)

    # Simulate rinse hold phase
    device_fixture["DummyWasher"]["state"]["status"]["value_raw"] = 11
    device_fixture["DummyWasher"]["state"]["status"]["value_localized"] = "Rinse hold"
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_raw"] = 262
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_localized"] = (
        "Rinse hold"
    )
    device_fixture["DummyWasher"]["state"]["remainingTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["remainingTime"][1] = 8
    device_fixture["DummyWasher"]["state"]["elapsedTime"][0] = 1
    device_fixture["DummyWasher"]["state"]["elapsedTime"][1] = 49

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    step += 1

    check_sensor_state(hass, "sensor.washing_machine", "rinse_hold", step)
    check_sensor_state(hass, "sensor.washing_machine_program", "minimum_iron", step)
    check_sensor_state(hass, "sensor.washing_machine_program_phase", "rinse_hold", step)
    check_sensor_state(hass, "sensor.washing_machine_target_temperature", "30.0", step)
    check_sensor_state(hass, "sensor.washing_machine_spin_speed", "1200", step)
    # RINSE HOLD -> elapsed, remaining time from API (normal case)
    check_sensor_state(hass, "sensor.washing_machine_remaining_time", "8", step)
    check_sensor_state(hass, "sensor.washing_machine_elapsed_time", "109", step)

    # Simulate program ended
    device_fixture["DummyWasher"]["state"]["status"]["value_raw"] = 7
    device_fixture["DummyWasher"]["state"]["status"]["value_localized"] = "Finished"
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_raw"] = 267
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_localized"] = (
        "Anti-crease"
    )
    device_fixture["DummyWasher"]["state"]["remainingTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["remainingTime"][1] = 0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][1] = 0
    device_fixture["DummyWasher"]["state"]["ecoFeedback"] = None

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    step += 1

    check_sensor_state(hass, "sensor.washing_machine", "program_ended", step)
    check_sensor_state(hass, "sensor.washing_machine_program", "minimum_iron", step)
    check_sensor_state(
        hass, "sensor.washing_machine_program_phase", "anti_crease", step
    )
    check_sensor_state(hass, "sensor.washing_machine_target_temperature", "30.0", step)
    check_sensor_state(hass, "sensor.washing_machine_spin_speed", "1200", step)
    # PROGRAM_ENDED -> remaining time forced to 0
    check_sensor_state(hass, "sensor.washing_machine_remaining_time", "0", step)
    # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
    check_sensor_state(hass, "sensor.washing_machine_elapsed_time", "109", step)
    # consumption values now are reporting last known value, API might start reporting null object
    check_sensor_state(hass, "sensor.washing_machine_energy_consumption", "0.1", step)
    check_sensor_state(hass, "sensor.washing_machine_water_consumption", "7", step)

    # Simulate when door is opened after program ended
    device_fixture["DummyWasher"]["state"]["status"]["value_raw"] = 3
    device_fixture["DummyWasher"]["state"]["status"]["value_localized"] = (
        "Programme selected"
    )
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_raw"] = 256
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_localized"] = ""
    device_fixture["DummyWasher"]["state"]["targetTemperature"][0]["value_raw"] = 4000
    device_fixture["DummyWasher"]["state"]["targetTemperature"][0][
        "value_localized"
    ] = 40.0
    device_fixture["DummyWasher"]["state"]["remainingTime"][0] = 1
    device_fixture["DummyWasher"]["state"]["remainingTime"][1] = 59
    device_fixture["DummyWasher"]["state"]["elapsedTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][1] = 0

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    step += 1

    check_sensor_state(hass, "sensor.washing_machine", "programmed", step)
    check_sensor_state(hass, "sensor.washing_machine_program", "minimum_iron", step)
    check_sensor_state(
        hass, "sensor.washing_machine_program_phase", "not_running", step
    )
    check_sensor_state(hass, "sensor.washing_machine_target_temperature", "40.0", step)
    check_sensor_state(hass, "sensor.washing_machine_spin_speed", "1200", step)
    # PROGRAMMED -> elapsed, remaining time from API (normal case)
    check_sensor_state(hass, "sensor.washing_machine_remaining_time", "119", step)
    check_sensor_state(hass, "sensor.washing_machine_elapsed_time", "0", step)


@pytest.mark.parametrize("load_device_file", ["laundry.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_laundry_dry_scenario(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    mock_config_entry: MockConfigEntry,
    device_fixture: MieleDevices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Parametrized test for verifying time sensors for tumble dryer devices when API reports time value from last cycle, when device is off."""

    step = 0

    # Initial state when the washing machine is off
    check_sensor_state(hass, "sensor.tumble_dryer", "off", step)
    check_sensor_state(hass, "sensor.tumble_dryer_program", "no_program", step)
    check_sensor_state(hass, "sensor.tumble_dryer_program_phase", "not_running", step)
    check_sensor_state(hass, "sensor.tumble_dryer_drying_step", "unknown", step)
    # OFF -> elapsed, remaining forced to unknown (some devices continue reporting last value of last cycle)
    check_sensor_state(hass, "sensor.tumble_dryer_remaining_time", "unknown", step)
    check_sensor_state(hass, "sensor.tumble_dryer_elapsed_time", "unknown", step)

    # Simulate program started
    device_fixture["DummyDryer"]["state"]["status"]["value_raw"] = 5
    device_fixture["DummyDryer"]["state"]["status"]["value_localized"] = "In use"
    device_fixture["DummyDryer"]["state"]["ProgramID"]["value_raw"] = 3
    device_fixture["DummyDryer"]["state"]["ProgramID"]["value_localized"] = (
        "Minimum iron"
    )
    device_fixture["DummyDryer"]["state"]["programPhase"]["value_raw"] = 514
    device_fixture["DummyDryer"]["state"]["programPhase"]["value_localized"] = "Drying"
    device_fixture["DummyDryer"]["state"]["remainingTime"][0] = 0
    device_fixture["DummyDryer"]["state"]["remainingTime"][1] = 49
    device_fixture["DummyDryer"]["state"]["elapsedTime"][0] = 0
    device_fixture["DummyDryer"]["state"]["elapsedTime"][1] = 20
    device_fixture["DummyDryer"]["state"]["dryingStep"]["value_raw"] = 2
    device_fixture["DummyDryer"]["state"]["dryingStep"]["value_localized"] = "Normal"

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    step += 1

    check_sensor_state(hass, "sensor.tumble_dryer", "in_use", step)
    check_sensor_state(hass, "sensor.tumble_dryer_program", "minimum_iron", step)
    check_sensor_state(hass, "sensor.tumble_dryer_program_phase", "drying", step)
    check_sensor_state(hass, "sensor.tumble_dryer_drying_step", "normal", step)
    # IN_USE -> elapsed, remaining time from API (normal case)
    check_sensor_state(hass, "sensor.tumble_dryer_remaining_time", "49", step)
    check_sensor_state(hass, "sensor.tumble_dryer_elapsed_time", "20", step)

    # Simulate program end
    device_fixture["DummyDryer"]["state"]["status"]["value_raw"] = 7
    device_fixture["DummyDryer"]["state"]["status"]["value_localized"] = "Finished"
    device_fixture["DummyDryer"]["state"]["programPhase"]["value_raw"] = 522
    device_fixture["DummyDryer"]["state"]["programPhase"]["value_localized"] = (
        "Finished"
    )
    device_fixture["DummyDryer"]["state"]["remainingTime"][0] = 0
    device_fixture["DummyDryer"]["state"]["remainingTime"][1] = 0
    device_fixture["DummyDryer"]["state"]["elapsedTime"][0] = 1
    device_fixture["DummyDryer"]["state"]["elapsedTime"][1] = 18

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    step += 1

    check_sensor_state(hass, "sensor.tumble_dryer", "program_ended", step)
    check_sensor_state(hass, "sensor.tumble_dryer_program", "minimum_iron", step)
    check_sensor_state(hass, "sensor.tumble_dryer_program_phase", "finished", step)
    check_sensor_state(hass, "sensor.tumble_dryer_drying_step", "normal", step)
    # PROGRAM_ENDED -> remaining time forced to 0
    check_sensor_state(hass, "sensor.tumble_dryer_remaining_time", "0", step)
    # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
    check_sensor_state(hass, "sensor.tumble_dryer_elapsed_time", "20", step)


@pytest.mark.parametrize("load_device_file", ["laundry.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_elapsed_time_sensor_restored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_miele_client: MagicMock,
    setup_platform: None,
    device_fixture: MieleDevices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that elapsed time returns the restored value when program ended."""

    entity_id = "sensor.washing_machine_elapsed_time"

    # Simulate program started
    device_fixture["DummyWasher"]["state"]["status"]["value_raw"] = 5
    device_fixture["DummyWasher"]["state"]["status"]["value_localized"] = "In use"
    device_fixture["DummyWasher"]["state"]["ProgramID"]["value_raw"] = 3
    device_fixture["DummyWasher"]["state"]["ProgramID"]["value_localized"] = (
        "Minimum iron"
    )
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_raw"] = 260
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_localized"] = (
        "Main wash"
    )
    device_fixture["DummyWasher"]["state"]["remainingTime"][0] = 1
    device_fixture["DummyWasher"]["state"]["remainingTime"][1] = 45
    device_fixture["DummyWasher"]["state"]["targetTemperature"][0]["value_raw"] = 3000
    device_fixture["DummyWasher"]["state"]["targetTemperature"][0][
        "value_localized"
    ] = 30.0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][1] = 12
    device_fixture["DummyWasher"]["state"]["spinningSpeed"]["value_raw"] = 1200
    device_fixture["DummyWasher"]["state"]["spinningSpeed"]["value_localized"] = "1200"

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "12"

    # Simulate program ended
    device_fixture["DummyWasher"]["state"]["status"]["value_raw"] = 7
    device_fixture["DummyWasher"]["state"]["status"]["value_localized"] = "Finished"
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_raw"] = 267
    device_fixture["DummyWasher"]["state"]["programPhase"]["value_localized"] = (
        "Anti-crease"
    )
    device_fixture["DummyWasher"]["state"]["remainingTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["remainingTime"][1] = 0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][0] = 0
    device_fixture["DummyWasher"]["state"]["elapsedTime"][1] = 0

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # unload config entry and reload to make sure that the state is restored

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # check that elapsed time is the one restored and not the value reported by API (0)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "12"
