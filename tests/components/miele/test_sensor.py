"""Tests for miele sensor module."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .mocks import mock_sensor_transitions

from tests.common import MockConfigEntry, snapshot_platform


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
            ],
            {
                "": ["off", "in_use", "rinse_hold"],
                "program": ["no_program", "minimum_iron", "minimum_iron"],
                "program_phase": ["not_running", "main_wash", "rinse_hold"],
                # "target_temperature": ["unknown", "30", "30"],
                "spin_speed": ["unknown", "1200", "1200"],
                "remaining_time": ["0", "105", "8"],
                # OFF -> elapsed forced to 0 (some devices continue reporting last value of last cycle)
                # IN_USE -> elapsed time from API (normal case)
                # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
                "elapsed_time": ["0", "12", "109"],
            },
        ),
        (
            "tumble_dryer",
            [],
            {
                "": ["off"],
                "program": ["no_program"],
                "program_phase": ["not_running"],
                "drying_step": ["unknown"],
                "remaining_time": ["0"],
                # OFF -> elapsed forced to 0 (some devices continue reporting last value of last cycle)
                # IN_USE -> elapsed time from API (normal case)
                # PROGRAM_ENDED -> elapsed time kept from last program (some devices immediately go to 0)
                "elapsed_time": ["0"],
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
