"""Tests for the Danfoss Air switch platform."""

from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
from pydanfossair.commands import UpdateCommand
import pytest
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

from . import setup_integration

ENTITY_BOOST = "switch.danfoss_air_boost"
ENTITY_BYPASS = "switch.danfoss_air_bypass"
ENTITY_AUTOMATIC_BYPASS = "switch.danfoss_air_automatic_bypass"


@pytest.mark.usefixtures("mock_danfoss_client")
@pytest.mark.parametrize(
    "entity_id", [ENTITY_BOOST, ENTITY_BYPASS, ENTITY_AUTOMATIC_BYPASS]
)
async def test_switch_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the switch states after the first poll."""
    await setup_integration(hass, freezer)

    assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    ("entity_id", "service", "command", "expected_state"),
    [
        pytest.param(
            ENTITY_BOOST,
            SERVICE_TURN_ON,
            UpdateCommand.boost_activate,
            STATE_ON,
            id="boost-on",
        ),
        pytest.param(
            ENTITY_BOOST,
            SERVICE_TURN_OFF,
            UpdateCommand.boost_deactivate,
            STATE_OFF,
            id="boost-off",
        ),
        pytest.param(
            ENTITY_BYPASS,
            SERVICE_TURN_ON,
            UpdateCommand.bypass_activate,
            STATE_ON,
            id="bypass-on",
        ),
        pytest.param(
            ENTITY_BYPASS,
            SERVICE_TURN_OFF,
            UpdateCommand.bypass_deactivate,
            STATE_OFF,
            id="bypass-off",
        ),
        pytest.param(
            ENTITY_AUTOMATIC_BYPASS,
            SERVICE_TURN_ON,
            UpdateCommand.automatic_bypass_activate,
            STATE_ON,
            id="automatic-bypass-on",
        ),
        pytest.param(
            ENTITY_AUTOMATIC_BYPASS,
            SERVICE_TURN_OFF,
            UpdateCommand.automatic_bypass_deactivate,
            STATE_OFF,
            id="automatic-bypass-off",
        ),
    ],
)
async def test_switch_commands(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_danfoss_client: MagicMock,
    entity_id: str,
    service: str,
    command: UpdateCommand,
    expected_state: str,
) -> None:
    """Test that each switch sends its own command and reflects the read-back state."""
    await setup_integration(hass, freezer)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    assert mock_danfoss_client.command.mock_calls[-1] == call(command)
    assert hass.states.get(entity_id).state == expected_state
