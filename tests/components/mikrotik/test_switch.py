"""Tests for the Mikrotik switch platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry
from .const import BRIDGE1_INTERFACE, ETHER1_INTERFACE, INTERFACE_DATA, WLAN1_INTERFACE

from tests.common import snapshot_platform


async def test_switch_entities_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Mikrotik switch entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        config_entry = await setup_mikrotik_entry(hass, interface_data=INTERFACE_DATA)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_no_matching_interfaces(hass: HomeAssistant) -> None:
    """Test no switch entities are created for unsupported interface types."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(hass, interface_data=[BRIDGE1_INTERFACE])

    assert hass.states.async_entity_ids(SWITCH_DOMAIN) == []


async def test_switch_turn_on(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test turning on a Mikrotik switch enables the interface."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(hass, interface_data=[dict(WLAN1_INTERFACE)])

    entity_id = "switch.wlan1_wlan"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api.assert_called_with("/interface/enable", **{".id": "*2"})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON


async def test_switch_turn_off(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test turning off a Mikrotik switch disables the interface."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SWITCH]):
        await setup_mikrotik_entry(hass, interface_data=[dict(ETHER1_INTERFACE)])

    entity_id = "switch.ether1_ethernet"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api.assert_called_with("/interface/disable", **{".id": "*1"})

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
