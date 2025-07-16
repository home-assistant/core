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


# @pytest.mark.parametrize("load_device_file", ["laundry_scenario/001_off.json"])
# @pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
# @pytest.mark.parametrize(
#     ("device_name", "json_sequence", "expected_sensor_states"),
#     [
#         (
#             "washing_machine",
#             [
#                 "laundry_scenario/002_washing.json",
#                 "laundry_scenario/003_rinse_hold.json",
#                 "laundry_scenario/004_wash_end.json",
#                 "laundry_scenario/005_drying.json",  # washer remains programmed while starting dryer
#             ],
#             {
#                 "": ["off", "in_use", "rinse_hold", "program_ended", "programmed"],
#                 "program": [
#                     "no_program",
#                     "minimum_iron",
#                     "minimum_iron",
#                     "minimum_iron",
#                     "minimum_iron",
#                 ],
#                 "program_phase": [
#                     "not_running",
#                     "main_wash",
#                     "rinse_hold",
#                     "anti_crease",
#                     "not_running",
#                 ],
#                 # "target_temperature": ["unknown", "30", "30", "30", "40"],
#                 "spin_speed": ["unknown", "1200", "1200", "1200", "1200"],
#                 "remaining_time": ["0", "105", "8", "0", "119"],
#                 # OFF -> elapsed forced to 0 (some devices continue reporting last value of last cycle)
#                 # IN_USE -> elapsed time from API (normal case)
#                 # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
#                 # PROGRAMMED -> elapsed time from API (normal case)
#                 "elapsed_time": ["0", "12", "109", "109", "0"],
#             },
#         ),
#         (
#             "tumble_dryer",
#             [
#                 "laundry_scenario/005_drying.json",
#                 "laundry_scenario/006_drying_end.json",
#             ],
#             {
#                 "": ["off", "in_use", "program_ended"],
#                 "program": ["no_program", "minimum_iron", "minimum_iron"],
#                 "program_phase": ["not_running", "drying", "finished"],
#                 "drying_step": ["unknown", "normal", "normal"],
#                 "remaining_time": ["0", "49", "0"],
#                 # OFF -> elapsed forced to 0 (some devices continue reporting last value of last cycle)
#                 # IN_USE -> elapsed time from API (normal case)
#                 # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
#                 "elapsed_time": ["0", "20", "20"],
#             },
#         ),
#     ],
# )

#     device_name: str,
#     json_sequence: list[str],
#     expected_sensor_states: dict[str, list[str]],
# ) -> None:
#     """Parametrized test for verifying sensor state transitions for laundry devices."""

#     await mock_sensor_transitions(
#         hass,
#         mock_miele_client,
#         mock_config_entry,
#         device_name,
#         json_sequence,
#         expected_sensor_states,
#     )


# @pytest.mark.parametrize("load_device_file", ["laundry_scenario/003_rinse_hold.json"])
# @pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
# async def test_elapsed_time_sensor_restored(


# ) -> None:
#     """Test that elapsed time returns the restored value when program ended."""

#     entity_id = "sensor.washing_machine_elapsed_time"

#     assert hass.states.get(entity_id).state == "109"

#     # load device when status is PROGRAM_ENDED and elapsed time reported by API is 0
#     mock_miele_client.get_devices.return_value = load_json_object_fixture(
#         "laundry_scenario/004_wash_end.json", DOMAIN
#     )

#     # unload config entry and reload to make sure that the state is restored


#     await hass.config_entries.async_unload(mock_config_entry.entry_id)
#     await hass.async_block_till_done()

#     assert hass.states.get(entity_id).state == "unavailable"

#     await hass.config_entries.async_reload(mock_config_entry.entry_id)
#     await hass.async_block_till_done()


#     # check that elapsed time is the one restored and not the value reported by API (0)
#     state = hass.states.get(entity_id)
#     assert state is not None
#     assert state.state == "109"
