"""Tests for Roborock vacuums."""


from typing import Any
from unittest.mock import patch

import pytest
from roborock.typing import RoborockCommand

from homeassistant.components.vacuum import (
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_START_PAUSE,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = "abc123"


async def test_registry_entries(
    hass: HomeAssistant, bypass_api_fixture, setup_entry: MockConfigEntry
) -> None:
    """Tests devices are registered in the entity registry."""
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID


@pytest.mark.parametrize(
    ("service", "command", "service_params", "called_params"),
    [
        (SERVICE_START, RoborockCommand.APP_START, None, None),
        (SERVICE_PAUSE, RoborockCommand.APP_PAUSE, None, None),
        (SERVICE_STOP, RoborockCommand.APP_STOP, None, None),
        (SERVICE_RETURN_TO_BASE, RoborockCommand.APP_CHARGE, None, None),
        (SERVICE_CLEAN_SPOT, RoborockCommand.APP_SPOT, None, None),
        (SERVICE_LOCATE, RoborockCommand.FIND_ME, None, None),
        (SERVICE_START_PAUSE, RoborockCommand.APP_START, None, None),
        (
            SERVICE_SET_FAN_SPEED,
            RoborockCommand.SET_CUSTOM_MODE,
            {"fan_speed": "silent"},
            [101],
        ),
        (
            SERVICE_SEND_COMMAND,
            RoborockCommand.GET_LED_STATUS,
            {"command": "get_led_status"},
            None,
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    bypass_api_fixture,
    setup_entry: MockConfigEntry,
    service: str,
    command: str,
    service_params: dict[str, Any],
    called_params: list | None,
) -> None:
    """Test sending commands to the vacuum."""

    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: ENTITY_ID, **(service_params or {})}
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.send_command"
    ) as mock_send_command:
        await hass.services.async_call(
            Platform.VACUUM,
            service,
            data,
            blocking=True,
        )
        assert mock_send_command.call_count == 1
        assert mock_send_command.call_args[0][0] == DEVICE_ID
        assert mock_send_command.call_args[0][1] == command
        assert mock_send_command.call_args[0][2] == called_params
