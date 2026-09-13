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
    NodeActionItemList,
    NodeListActionItemList,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

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

from . import async_fire_coordinator_update, setup_platform_integration

from tests.common import MockConfigEntry, async_fire_time_changed

_IDENTIFY_ENTITY = "switch.living_identify"


def _build_node_actions(
    *, val_type: ActionValueType = ActionValueType.BOOLEAN
) -> NodeListActionItemList:
    """Build node action discovery data for switch tests."""
    return NodeListActionItemList(
        nodes=[
            NodeActionItemList(
                node_id=1,
                actions=[
                    ActionItem(
                        action=KnownActionName.SET_IDENTIFY,
                        val_type=val_type,
                    )
                ],
            )
        ]
    )


async def _async_set_identify(hass: HomeAssistant, service: str) -> None:
    """Set the identify switch state."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: _IDENTIFY_ENTITY},
        blocking=True,
    )


async def test_identify_switch_discovery_and_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test identify switches require a Boolean identify action."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions()

    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    state = hass.states.get(_IDENTIFY_ENTITY)
    assert state is not None
    assert state.state == STATE_OFF

    assert hass.states.get("switch.office_co2_identify") is None


async def test_non_boolean_identify_action_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test identify actions with another value type are ignored."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions(
        val_type=ActionValueType.INTEGER
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    assert hass.states.get(_IDENTIFY_ENTITY) is None


async def test_turn_identify_on_and_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
) -> None:
    """Test identify writes use the typed helper and targeted readback."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions()
    box_node = mock_nodes[0]
    mock_duco_client.async_get_node_info.side_effect = [
        replace(
            box_node,
            general=replace(box_node.general, identify=1),
        ),
        box_node,
    ]
    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    await _async_set_identify(hass, SERVICE_TURN_ON)

    mock_duco_client.async_set_node_identify.assert_awaited_once_with(1, True)
    state = hass.states.get(_IDENTIFY_ENTITY)
    assert state is not None
    assert state.state == STATE_ON

    await _async_set_identify(hass, SERVICE_TURN_OFF)

    mock_duco_client.async_set_node_identify.assert_awaited_with(1, False)
    assert mock_duco_client.async_get_node_info.await_count == 2
    assert mock_duco_client.async_get_nodes.await_count == 1
    state = hass.states.get(_IDENTIFY_ENTITY)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        pytest.param(
            DucoError("Unexpected error"), "Failed to set node identification"
        ),
        pytest.param(DucoRateLimitError(), "daily write limit"),
    ],
)
async def test_identify_write_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    exception: Exception,
    match: str,
) -> None:
    """Test identify write failures raise translated Home Assistant errors."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions()
    mock_duco_client.async_set_node_identify.side_effect = exception
    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    with pytest.raises(HomeAssistantError, match=match):
        await _async_set_identify(hass, SERVICE_TURN_ON)


async def test_identify_switch_is_added_when_action_discovery_succeeds_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test identify switches are added after action discovery recovers."""
    mock_duco_client.async_get_node_actions.side_effect = [
        DucoError("Connection refused"),
        _build_node_actions(),
    ]
    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    assert hass.states.get(_IDENTIFY_ENTITY) is None

    await async_fire_coordinator_update(hass, freezer)

    assert hass.states.get(_IDENTIFY_ENTITY) is not None


async def test_identify_switch_becomes_unavailable_when_node_is_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an identify switch becomes unavailable when its node disappears."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions()
    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])
    mock_duco_client.async_get_nodes.return_value = mock_nodes[1:]

    await async_fire_coordinator_update(hass, freezer)

    state = hass.states.get(_IDENTIFY_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_targeted_identify_readback_keeps_coordinator_poll_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an identify readback does not postpone the full coordinator poll."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions()
    box_node = mock_nodes[0]
    mock_duco_client.async_get_node_info.return_value = replace(
        box_node, general=replace(box_node.general, identify=1)
    )
    mock_duco_client.async_get_node_info.side_effect = None
    await setup_platform_integration(hass, mock_config_entry, [Platform.SWITCH])

    freezer.tick(SCAN_INTERVAL / 2)
    await _async_set_identify(hass, SERVICE_TURN_ON)

    freezer.tick(SCAN_INTERVAL / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_duco_client.async_get_nodes.await_count == 2
