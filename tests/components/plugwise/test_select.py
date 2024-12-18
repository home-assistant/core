"""Tests for the Plugwise Select integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


async def test_adam_select_entities(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test a thermostat Select."""

    state = hass.states.get("select.woonkamer_thermostat_schedule")
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
            ATTR_ENTITY_ID: "select.woonkamer_thermostat_schedule",
            ATTR_OPTION: "Badkamer Schema",
        },
        blocking=True,
    )

    assert mock_smile_adam.set_select.call_count == 1
    mock_smile_adam.set_select.assert_called_with(
        "select_schedule",
        "c50f167537524366a5af7aa3942feb1e",
        "Badkamer Schema",
        "on",
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
            ATTR_ENTITY_ID: "select.adam_regulation_mode",
            ATTR_OPTION: "heating",
        },
        blocking=True,
    )
    assert mock_smile_adam_3.set_select.call_count == 1
    mock_smile_adam_3.set_select.assert_called_with(
        "select_regulation_mode",
        "bc93488efab249e5bc54fd7e175a6f91",
        "heating",
        "on",
    )


async def test_legacy_anna_select_entities(
    hass: HomeAssistant,
    mock_smile_legacy_anna: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test not creating a select-entity for a legacy Anna without a thermostat-schedule."""
    assert not hass.states.get("select.anna_thermostat_schedule")


async def test_adam_select_unavailable_regulation_mode(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test a regulation_mode non-available preset."""

    with pytest.raises(ServiceValidationError, match="valid options"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.anna_thermostat_schedule",
                ATTR_OPTION: "freezing",
            },
            blocking=True,
        )
