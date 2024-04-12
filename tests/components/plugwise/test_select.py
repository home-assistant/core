"""Tests for the Plugwise Select integration."""

from unittest.mock import MagicMock

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_adam_select_entities(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test a thermostat Select."""

    state = hass.states.get("select.zone_lisa_wk_thermostat_schedule")
    assert state
    assert state.state == "GF7  Woonkamer"


async def test_adam_change_select_entity(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of select entities."""

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.zone_lisa_wk_thermostat_schedule",
            ATTR_OPTION: "Badkamer Schema",
        },
        blocking=True,
    )

    assert mock_smile_adam.set_schedule_state.call_count == 1
    mock_smile_adam.set_schedule_state.assert_called_with(
        "c50f167537524366a5af7aa3942feb1e",
        "on",
        "Badkamer Schema",
    )


async def test_adam_select_regulation_mode(
    hass: HomeAssistant, mock_smile_adam_3: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test a regulation_mode select.

    Also tests a change in climate _previous mode.
    """

    state = hass.states.get("select.adam_gateway_mode")
    assert state
    assert state.state == "full"
    state = hass.states.get("select.adam_regulation_mode")
    assert state
    assert state.state == "cooling"
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            "entity_id": "select.adam_regulation_mode",
            "option": "heating",
        },
        blocking=True,
    )
    assert mock_smile_adam_3.set_regulation_mode.call_count == 1
    mock_smile_adam_3.set_regulation_mode.assert_called_with("heating")
