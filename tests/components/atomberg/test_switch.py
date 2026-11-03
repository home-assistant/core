"""Tests for the Atomberg sleep mode switch."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

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

SWITCH = "switch.living_room_sleep_mode"


@pytest.mark.parametrize(
    ("service", "enabled", "state"),
    [
        (SERVICE_TURN_ON, True, STATE_ON),
        (SERVICE_TURN_OFF, False, STATE_OFF),
    ],
)
async def test_sleep_switch(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    enabled: bool,
    state: str,
) -> None:
    """Test toggling sleep mode."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(SWITCH).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: SWITCH}, blocking=True
    )

    mock_client.async_send_command.assert_awaited_once_with(
        "a4cf12abcdef", {"sleep": enabled}
    )
    assert hass.states.get(SWITCH).state == state
