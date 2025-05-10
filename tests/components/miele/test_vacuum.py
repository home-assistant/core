"""Tests for miele vacuum module."""

from unittest.mock import MagicMock

from aiohttp import ClientResponseError
from pymiele import MieleDevices
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN, PROCESS_ACTION, PROGRAM_ID
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_PAUSE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import get_actions_callback, get_data_callback

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform

TEST_PLATFORM = VACUUM_DOMAIN
ENTITY_ID = "vacuum.robot_vacuum_cleaner"

pytestmark = [
    pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)]),
    pytest.mark.parametrize("load_device_file", ["vacuum_device.json"]),
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test vacuum entity setup."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_vacuum_states_api_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
    device_fixture: MieleDevices,
) -> None:
    """Test vacuum state when the API pushes data via SSE."""

    data_callback = get_data_callback(mock_miele_client)
    await data_callback(device_fixture)
    await hass.async_block_till_done()

    act_file = load_json_object_fixture("action_push_vacuum.json", DOMAIN)
    action_callback = get_actions_callback(mock_miele_client)
    await action_callback(act_file)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize(
    ("service", "action_command", "vacuum_power"),
    [
        (SERVICE_START, PROCESS_ACTION, 1),
        (SERVICE_STOP, PROCESS_ACTION, 2),
        (SERVICE_PAUSE, PROCESS_ACTION, 3),
        (SERVICE_CLEAN_SPOT, PROGRAM_ID, 2),
    ],
)
async def test_vacuum_program(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    service: str,
    vacuum_power: int | str,
    action_command: str,
) -> None:
    """Test the vacuum can be controlled."""

    await hass.services.async_call(
        TEST_PLATFORM, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_miele_client.send_action.assert_called_once_with(
        "Dummy_Vacuum_1", {action_command: vacuum_power}
    )


@pytest.mark.parametrize(
    ("fan_speed", "expected"), [("normal", 1), ("turbo", 3), ("silent", 4)]
)
async def test_vacuum_fan_speed(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    fan_speed: str,
    expected: int,
) -> None:
    """Test the vacuum can be controlled."""

    await hass.services.async_call(
        TEST_PLATFORM,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_SPEED: fan_speed},
        blocking=True,
    )
    mock_miele_client.send_action.assert_called_once_with(
        "Dummy_Vacuum_1", {"programId": expected}
    )


@pytest.mark.parametrize(
    ("service"),
    [
        (SERVICE_START),
        (SERVICE_STOP),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    service: str,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.send_action.side_effect = ClientResponseError("test", "Test")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    mock_miele_client.send_action.assert_called_once()
