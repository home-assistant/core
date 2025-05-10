"""Tests for miele switch module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
from pymiele import MieleDevices
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import get_actions_callback, get_data_callback

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform

TEST_PLATFORM = SWITCH_DOMAIN
pytestmark = pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)])

ENTITY_ID = "switch.freezer_superfreezing"


async def test_switch_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test switch entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_states_api_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
    device_fixture: MieleDevices,
) -> None:
    """Test switch state when the API pushes data via SSE."""

    data_callback = get_data_callback(mock_miele_client)
    await data_callback(device_fixture)
    await hass.async_block_till_done()

    act_file = load_json_object_fixture("4_actions.json", DOMAIN)
    action_callback = get_actions_callback(mock_miele_client)
    await action_callback(act_file)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize(
    ("entity"),
    [
        (ENTITY_ID),
        ("switch.refrigerator_supercooling"),
        ("switch.washing_machine_power"),
    ],
)
@pytest.mark.parametrize(
    ("service"),
    [
        (SERVICE_TURN_ON),
        (SERVICE_TURN_OFF),
    ],
)
async def test_switching(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
    service: str,
    entity: str,
) -> None:
    """Test the switch can be turned on/off."""

    await hass.services.async_call(
        TEST_PLATFORM, service, {ATTR_ENTITY_ID: entity}, blocking=True
    )
    mock_miele_client.send_action.assert_called_once()


@pytest.mark.parametrize(
    ("entity"),
    [
        (ENTITY_ID),
        ("switch.refrigerator_supercooling"),
        ("switch.washing_machine_power"),
    ],
)
@pytest.mark.parametrize(
    ("service"),
    [
        (SERVICE_TURN_ON),
        (SERVICE_TURN_OFF),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
    service: str,
    entity: str,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.send_action.side_effect = ClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM, service, {ATTR_ENTITY_ID: entity}, blocking=True
        )
    mock_miele_client.send_action.assert_called_once()
