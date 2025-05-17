"""Tests for miele sensor module."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .mocks import mock_sensor_transitions

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test sensor state."""

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


@pytest.mark.parametrize("load_device_file", ["laundry_scenario/001_off.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_name", "json_sequence", "expected_sensor_states"),
    [
        (
            "washing_machine",
            [
                "laundry_scenario/002_washing.json",
                "laundry_scenario/003_rinse_hold.json",
                "laundry_scenario/004_wash_end.json",
                "laundry_scenario/005_drying.json",  # washer remains programmed while starting dryer
            ],
            {
                "": ["off", "in_use", "rinse_hold", "program_ended", "programmed"],
                "program": [
                    "no_program",
                    "minimum_iron",
                    "minimum_iron",
                    "minimum_iron",
                    "minimum_iron",
                ],
                "program_phase": [
                    "not_running",
                    "main_wash",
                    "rinse_hold",
                    "anti_crease",
                    "not_running",
                ],
                # "target_temperature": ["unknown", "30", "30", "30", "40"],
                "spin_speed": ["unknown", "1200", "1200", "1200", "1200"],
                "remaining_time": ["0", "105", "8", "0", "119"],
                # OFF -> elapsed forced to 0 (some devices continue reporting last value of last cycle)
                # IN_USE -> elapsed time from API (normal case)
                # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
                # PROGRAMMED -> elapsed time from API (normal case)
                "elapsed_time": ["0", "12", "109", "109", "0"],
            },
        ),
        (
            "tumble_dryer",
            [
                "laundry_scenario/005_drying.json",
            ],
            {
                "": ["off", "in_use"],
                "program": ["no_program", "minimum_iron"],
                "program_phase": ["not_running", "drying"],
                "drying_step": ["unknown", "normal"],
                "remaining_time": ["0", "49"],
                # OFF -> elapsed forced to 0 (some devices continue reporting last value of last cycle)
                # IN_USE -> elapsed time from API (normal case)
                # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
                "elapsed_time": ["0", "20"],
            },
        ),
    ],
)
async def test_laundry_scenario(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    json_sequence: list[str],
    expected_sensor_states: dict[str, list[str]],
) -> None:
    """Parametrized test for verifying sensor state transitions for laundry devices."""

    await mock_sensor_transitions(
        hass,
        mock_miele_client,
        mock_config_entry,
        device_name,
        json_sequence,
        expected_sensor_states,
    )


@pytest.mark.parametrize("load_device_file", ["laundry_scenario/003_rinse_hold.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_elapsed_time_sensor_restored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test that elapsed time returns the restored value when program ended."""

    entity_id = "sensor.washing_machine_elapsed_time"

    assert hass.states.get(entity_id).state == "109"

    # load device when status is PROGRAM_ENDED and elapsed time reported by API is 0
    mock_miele_client.get_devices.return_value = load_json_object_fixture(
        "laundry_scenario/004_wash_end.json", DOMAIN
    )

    # unload config entry and reload to make sure that the state is restored
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # check that elapsed time is the one restored and not the value reported by API (0)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "109"
