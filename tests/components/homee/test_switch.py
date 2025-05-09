"""Test Homee switches."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from websockets import frames
from websockets.exceptions import ConnectionClosed

from homeassistant.components.homee.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    SwitchDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switch_state(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the correct state is returned."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch_switch_1").state is not STATE_ON
    switch = mock_homee.nodes[0].attributes[2]
    switch.current_value = 1
    switch.add_on_changed_listener.call_args_list[0][0][0](switch)
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_switch_switch_1").state is STATE_ON


async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-on service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch_switch_1").state is not STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_switch_switch_1"},
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(1, 3, 1)


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-off service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch_watchdog").state is STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_watchdog"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 5, 0)


async def test_switch_device_class(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if device class gets set correctly."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("switch.test_switch_switch_1").attributes["device_class"]
        == SwitchDeviceClass.OUTLET
    )
    assert (
        hass.states.get("switch.test_switch_watchdog").attributes["device_class"]
        == SwitchDeviceClass.SWITCH
    )


async def test_switch_no_name(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch gets no name when it is the main feature of the device."""
    mock_homee.nodes = [build_mock_node("switch_single.json")]
    mock_homee.nodes[0].profile = 2002
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("switch.test_switch_single").attributes["friendly_name"]
        == "Test Switch Single"
    )


async def test_switch_device_class_no_outlet(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if on_off device class gets set correctly if node-profile is not a plug."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.nodes[0].profile = 2002
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("switch.test_switch_switch_1").attributes["device_class"]
        == SwitchDeviceClass.SWITCH
    )


async def test_send_error(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test failed set_value command."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    await setup_integration(hass, mock_config_entry)

    mock_homee.set_value.side_effect = ConnectionClosed(
        rcvd=frames.Close(1002, "Protocol Error"), sent=None
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.test_switch_switch_1"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "connection_closed"


async def test_switch_snapshot(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the multisensor snapshot."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    mock_homee.get_node_by_id.return_value = mock_homee.nodes[0]
    with patch("homeassistant.components.homee.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
