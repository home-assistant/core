"""Tests for the Mikrotik select platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mikrotik.const import INTERFACE, MIKROTIK_SERVICES, POE
from homeassistant.components.mikrotik.select import SELECTS, MikrotikSelectEntity
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry
from .const import BRIDGE1_INTERFACE, ETHER1_INTERFACE, ETHER1_POE, INTERFACE_DATA

from tests.common import snapshot_platform


async def test_select_entities_created(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Mikrotik select entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SELECT]):
        config_entry = await setup_mikrotik_entry(
            hass, interface_data=INTERFACE_DATA, poe_data=[ETHER1_POE]
        )

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_select_no_matching_interfaces(hass: HomeAssistant) -> None:
    """Test no select entities are created for interfaces without PoE support."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SELECT]):
        await setup_mikrotik_entry(hass, interface_data=[BRIDGE1_INTERFACE])

    assert hass.states.async_entity_ids(SELECT_DOMAIN) == []


async def test_select_option(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test selecting a PoE option updates the Mikrotik interface."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SELECT]):
        await setup_mikrotik_entry(
            hass,
            interface_data=[dict(ETHER1_INTERFACE)],
            poe_data=[ETHER1_POE],
        )

    entity_id = "select.ether1_poe_out"
    assert (state := hass.states.get(entity_id))
    assert state.state == "auto_on"

    def command_side_effect(cmd: str, **params: Any) -> list[dict[str, Any]]:
        """Reflect the PoE change the coordinator refresh will pick up."""
        if cmd == MIKROTIK_SERVICES[INTERFACE]:
            return [ETHER1_INTERFACE]
        if cmd == MIKROTIK_SERVICES[POE]:
            return [{**ETHER1_POE, "poe-out": "forced-on"}]
        return []

    mock_api.side_effect = command_side_effect

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "forced_on"},
        blocking=True,
    )

    mock_api.assert_any_call(
        "/interface/ethernet/poe/set", **{".id": "*1", "poe-out": "forced-on"}
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == "forced_on"


async def test_current_option_none_without_poe_state(hass: HomeAssistant) -> None:
    """Test current_option is None for an interface without a reported PoE state."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.SELECT]):
        config_entry = await setup_mikrotik_entry(
            hass,
            interface_data=[dict(ETHER1_INTERFACE)],
            poe_data=[ETHER1_POE],
        )

    entity = MikrotikSelectEntity(
        config_entry,
        config_entry.runtime_data,
        SELECTS[0],
        dict(ETHER1_INTERFACE),
    )

    assert entity.current_option is None
