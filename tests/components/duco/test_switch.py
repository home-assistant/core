"""Tests for the Duco switch platform."""

from dataclasses import replace
from unittest.mock import AsyncMock

from duco_connectivity import (
    ActionItem,
    ActionValueType,
    DucoError,
    DucoRateLimitError,
    KnownActionName,
    Node,
    NodeListActionItemList,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import SCAN_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import async_fire_coordinator_update, setup_platform_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

_IDENTIFY_ENTITY = "switch.living_identify"


def _identify_action(
    val_type: ActionValueType = ActionValueType.BOOLEAN,
) -> ActionItem:
    """Build identify action metadata for switch tests."""
    return ActionItem(
        action=KnownActionName.SET_IDENTIFY,
        val_type=val_type,
    )


async def _async_set_identify(hass: HomeAssistant, service: str) -> None:
    """Set the identify switch state."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: _IDENTIFY_ENTITY},
        blocking=True,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_node_actions: NodeListActionItemList,
) -> None:
    """Set up only the switch platform with identify capability."""
    mock_node_actions.nodes[0].actions.append(_identify_action())
    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])


@pytest.mark.usefixtures("init_integration")
async def test_identify_switch_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the identify switch entity registry metadata and state."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_identify_switch_discovery_and_state(hass: HomeAssistant) -> None:
    """Test identify switches require a Boolean identify action."""
    assert hass.states.is_state(_IDENTIFY_ENTITY, STATE_OFF)
    assert hass.states.get("switch.office_co2_identify") is None


async def test_non_boolean_identify_action_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_node_actions: NodeListActionItemList,
) -> None:
    """Test identify actions with another value type are ignored."""
    mock_node_actions.nodes[0].actions.append(_identify_action(ActionValueType.INTEGER))

    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    assert hass.states.get(_IDENTIFY_ENTITY) is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "identify", "expected_state"),
    [
        pytest.param(SERVICE_TURN_ON, True, STATE_ON, id="on"),
        pytest.param(SERVICE_TURN_OFF, False, STATE_OFF, id="off"),
    ],
)
async def test_set_identify(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    service: str,
    identify: bool,
    expected_state: str,
) -> None:
    """Test identify writes use the typed helper and update state."""
    box_node = mock_nodes[0]
    mock_duco_client.async_get_node_info.side_effect = None
    mock_duco_client.async_get_node_info.return_value = replace(
        box_node,
        general=replace(box_node.general, identify=int(identify)),
    )

    await _async_set_identify(hass, service)

    mock_duco_client.async_set_node_identify.assert_awaited_once_with(1, identify)
    mock_duco_client.async_get_node_info.assert_awaited_once_with(1)
    assert mock_duco_client.async_get_nodes.await_count == 1
    assert hass.states.is_state(_IDENTIFY_ENTITY, expected_state)


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        pytest.param(
            DucoError("Unexpected error"), "Failed to set node identification"
        ),
        pytest.param(DucoRateLimitError(), "daily write limit"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_identify_write_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
    match: str,
) -> None:
    """Test identify write failures report user-facing errors."""
    mock_duco_client.async_set_node_identify.side_effect = exception

    with pytest.raises(HomeAssistantError, match=match):
        await _async_set_identify(hass, SERVICE_TURN_ON)


async def test_identify_switch_is_added_when_action_discovery_succeeds_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_node_actions: NodeListActionItemList,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test identify switches are added after action discovery recovers."""
    mock_node_actions.nodes[0].actions.append(_identify_action())
    mock_duco_client.async_get_node_actions.side_effect = [
        DucoError("Connection refused"),
        mock_node_actions,
    ]
    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    assert hass.states.get(_IDENTIFY_ENTITY) is None

    await async_fire_coordinator_update(hass, freezer)

    assert hass.states.get(_IDENTIFY_ENTITY) is not None


@pytest.mark.usefixtures("init_integration")
async def test_identify_switch_becomes_unavailable_when_node_is_missing(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an identify switch becomes unavailable when its node disappears."""
    mock_duco_client.async_get_nodes.return_value = mock_nodes[1:]

    await async_fire_coordinator_update(hass, freezer)

    assert hass.states.is_state(_IDENTIFY_ENTITY, STATE_UNAVAILABLE)


@pytest.mark.usefixtures("init_integration")
async def test_targeted_identify_readback_keeps_coordinator_poll_schedule(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an identify readback does not postpone the full coordinator poll."""
    box_node = mock_nodes[0]
    mock_duco_client.async_get_node_info.return_value = replace(
        box_node, general=replace(box_node.general, identify=1)
    )
    mock_duco_client.async_get_node_info.side_effect = None

    freezer.tick(SCAN_INTERVAL / 2)
    await _async_set_identify(hass, SERVICE_TURN_ON)

    freezer.tick(SCAN_INTERVAL / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_duco_client.async_get_nodes.await_count == 2
