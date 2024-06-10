"""Tests for switch platform."""

from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerStates, RestrictedReasons
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
    snapshot_platform,
)

TEST_ZONE_ID = "AAAAAAAA-BBBB-CCCC-DDDD-123456789101"


async def test_switch_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch state."""
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    for state, restricted_reson, expected_state in [
        (MowerStates.RESTRICTED, RestrictedReasons.NOT_APPLICABLE, "off"),
        (MowerStates.IN_OPERATION, RestrictedReasons.NONE, "on"),
    ]:
        values[TEST_MOWER_ID].mower.state = state
        values[TEST_MOWER_ID].planner.restricted_reason = restricted_reson
        mock_automower_client.get_status.return_value = values
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        state = hass.states.get("switch.test_mower_1_enable_schedule")
        assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "aioautomower_command"),
    [
        ("turn_off", "park_until_further_notice"),
        ("turn_on", "resume_schedule"),
        ("toggle", "park_until_further_notice"),
    ],
)
async def test_switch_commands(
    hass: HomeAssistant,
    aioautomower_command: str,
    service: str,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch commands."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        domain="switch",
        service=service,
        service_data={"entity_id": "switch.test_mower_1_enable_schedule"},
        blocking=True,
    )
    mocked_method = getattr(mock_automower_client.commands, aioautomower_command)
    mocked_method.assert_called_once_with(TEST_MOWER_ID)

    mocked_method.side_effect = ApiException("Test error")
    with pytest.raises(
        HomeAssistantError,
        match="Command couldn't be sent to the command queue: Test error",
    ):
        await hass.services.async_call(
            domain="switch",
            service=service,
            service_data={"entity_id": "switch.test_mower_1_enable_schedule"},
            blocking=True,
        )
    assert len(mocked_method.mock_calls) == 2


@pytest.mark.parametrize(
    ("service", "boolean", "excepted_state"),
    [
        ("turn_off", False, "off"),
        ("turn_on", True, "on"),
        ("toggle", True, "on"),
    ],
)
async def test_stay_out_zone_switch_commands(
    hass: HomeAssistant,
    service: str,
    boolean: bool,
    excepted_state: str,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch commands."""
    entity_id = "switch.test_mower_1_avoid_danger_zone"
    await setup_integration(hass, mock_config_entry)
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    values[TEST_MOWER_ID].stay_out_zones.zones[TEST_ZONE_ID].enabled = boolean
    mock_automower_client.get_status.return_value = values
    mocked_method = AsyncMock()
    setattr(mock_automower_client.commands, "switch_stay_out_zone", mocked_method)
    await hass.services.async_call(
        domain="switch",
        service=service,
        service_data={"entity_id": entity_id},
        blocking=True,
    )
    mocked_method.assert_called_once_with(TEST_MOWER_ID, TEST_ZONE_ID, boolean)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == excepted_state

    mocked_method.side_effect = ApiException("Test error")
    with pytest.raises(
        HomeAssistantError,
        match="Command couldn't be sent to the command queue: Test error",
    ):
        await hass.services.async_call(
            domain="switch",
            service=service,
            service_data={"entity_id": entity_id},
            blocking=True,
        )
    assert len(mocked_method.mock_calls) == 2


async def test_zones_deleted(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test if stay-out-zone is deleted after removed."""

    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)
    current_entries = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    del values[TEST_MOWER_ID].stay_out_zones.zones[TEST_ZONE_ID]
    mock_automower_client.get_status.return_value = values
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    ) == (current_entries - 1)


async def test_switch_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot tests of the switches."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )
