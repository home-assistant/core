"""Tests for the AquaLogic switch platform."""

from unittest.mock import MagicMock

from aqualogic.core import States
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aqualogic import DOMAIN, AquaLogicProcessor
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
async def init_switches(
    hass: HomeAssistant, init_integration: AquaLogicProcessor
) -> None:
    """Set up the AquaLogic switch platform."""
    assert await async_setup_component(
        hass,
        "switch",
        {"switch": {"platform": DOMAIN}},
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_switches")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all switch entities are created and report correct state."""
    states = {
        state.entity_id: state
        for state in sorted(hass.states.async_all("switch"), key=lambda s: s.entity_id)
    }
    assert states == snapshot


@pytest.mark.usefixtures("init_switches")
@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        pytest.param(SERVICE_TURN_ON, True, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, False, id="turn_off"),
    ],
)
async def test_turn(
    hass: HomeAssistant,
    mock_panel: MagicMock,
    service: str,
    expected_state: bool,
) -> None:
    """Test turning a switch on/off calls set_state on the panel."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.aqualogic_lights"},
        blocking=True,
    )
    mock_panel.set_state.assert_called_once_with(States.LIGHTS, expected_state)
