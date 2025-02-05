"""Test Homee switches."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    SwitchDeviceClass,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import build_mock_node, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switch_on(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-on service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch").state is not STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_switch"},
        blocking=True,
    )

    mock_homee.set_value.assert_called_once_with(1, 11, 1)


async def test_switch_off(
    hass: HomeAssistant,
    mock_homee: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turn-off service."""
    mock_homee.nodes = [build_mock_node("switches.json")]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.test_switch_identification_mode").state is STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_identification_mode"},
        blocking=True,
    )
    mock_homee.set_value.assert_called_once_with(1, 4, 0)


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
        hass.states.get("switch.test_switch").attributes["device_class"]
        == SwitchDeviceClass.OUTLET
    )
    assert (
        hass.states.get("switch.test_switch_impulse_2").attributes["device_class"]
        == SwitchDeviceClass.SWITCH
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
        hass.states.get("switch.test_switch").attributes["device_class"]
        == SwitchDeviceClass.SWITCH
    )


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
