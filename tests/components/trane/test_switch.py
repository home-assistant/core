"""Tests for the Trane Local switch platform."""

from unittest.mock import MagicMock

import pytest
from steamloop import HoldType
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot all switch entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_hold_switch_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test hold switch reports on when in permanent hold."""
    state = hass.states.get("switch.living_room_hold")
    assert state is not None
    assert state.state == STATE_ON


async def test_hold_switch_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test hold switch reports off when following schedule."""
    mock_connection.state.zones["1"].hold_type = HoldType.SCHEDULE

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.living_room_hold")
    assert state is not None
    assert state.state == STATE_OFF


async def test_turn_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test turning on the hold switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.living_room_hold"},
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1", hold_type=HoldType.MANUAL
    )


async def test_turn_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MagicMock,
) -> None:
    """Test turning off the hold switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.living_room_hold"},
        blocking=True,
    )

    mock_connection.set_temperature_setpoint.assert_called_once_with(
        "1", hold_type=HoldType.SCHEDULE
    )
