"""Tests for the KEBA charging station switch platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

SWITCH_ENTITY_ID = "switch.kc_p30_charging_enabled"


@pytest.mark.usefixtures("init_integration")
async def test_switch_entity_created(hass: HomeAssistant) -> None:
    """Test that the switch entity is created."""
    assert hass.states.get(SWITCH_ENTITY_ID) is not None


@pytest.mark.usefixtures("init_integration")
async def test_switch_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the switch state matches snapshot."""
    assert hass.states.get(SWITCH_ENTITY_ID) == snapshot


@pytest.mark.usefixtures("init_integration")
async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test turning the switch on calls async_enable_ev."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": SWITCH_ENTITY_ID},
        blocking=True,
    )
    mock_keba.async_enable_ev.assert_called_once()


@pytest.mark.usefixtures("init_integration")
async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_keba: MagicMock,
) -> None:
    """Test turning the switch off calls async_disable_ev."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": SWITCH_ENTITY_ID},
        blocking=True,
    )
    mock_keba.async_disable_ev.assert_called_once()
