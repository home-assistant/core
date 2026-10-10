"""Tests for the AquaLogic switch platform."""

from unittest.mock import MagicMock

from aqualogic.core import States
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aqualogic.const import UPDATE_TOPIC
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures("init_integration")
async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch entities are created and report correct state."""
    async_dispatcher_send(hass, UPDATE_TOPIC)
    await hass.async_block_till_done()

    states = {
        state.entity_id: state
        for state in sorted(hass.states.async_all("switch"), key=lambda s: s.entity_id)
    }
    assert states == snapshot


@pytest.mark.usefixtures("init_integration")
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


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "service",
    [
        pytest.param(SERVICE_TURN_ON, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, id="turn_off"),
    ],
)
async def test_turn_no_panel(
    hass: HomeAssistant,
    mock_processor: MagicMock,
    service: str,
) -> None:
    """Test that turning a switch does nothing when the panel is unavailable."""
    panel = mock_processor.panel
    mock_processor.panel = None
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.aqualogic_lights"},
        blocking=True,
    )
    panel.set_state.assert_not_called()


@pytest.mark.usefixtures("init_integration")
async def test_is_on_no_panel(
    hass: HomeAssistant,
    mock_processor: MagicMock,
) -> None:
    """Test switch reports off when panel is unavailable."""
    mock_processor.panel = None
    async_dispatcher_send(hass, UPDATE_TOPIC)
    await hass.async_block_till_done()

    assert hass.states.get("switch.aqualogic_lights").state == STATE_OFF
