"""Tests for the MotionMount Select platform."""

import socket
from unittest.mock import MagicMock

import motionmount
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

PRESET_ENTITY_ID = "select.my_motionmount_preset"


@pytest.fixture
def mock_presets(mock_motionmount: MagicMock) -> MagicMock:
    """Return a MotionMount mock with a stored preset."""
    mock_motionmount.is_authenticated = True
    mock_motionmount.is_moving = False
    mock_motionmount.extension = 0
    mock_motionmount.turn = 0
    mock_motionmount.get_presets.return_value = [motionmount.Preset(1, "Couch", 50, 25)]
    return mock_motionmount


async def test_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_presets: MagicMock,
) -> None:
    """Test selecting a preset."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: PRESET_ENTITY_ID, ATTR_OPTION: "Couch"},
        blocking=True,
    )

    mock_presets.go_to_preset.assert_awaited_once_with(1)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ConnectionResetError, id="connection_reset"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(socket.gaierror, id="gaierror"),
        pytest.param(motionmount.NotConnectedError, id="not_connected"),
    ],
)
async def test_select_option_communication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_presets: MagicMock,
    exception: type[Exception],
) -> None:
    """Test a communication error while selecting a preset raises HomeAssistantError."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    mock_presets.go_to_preset.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: PRESET_ENTITY_ID, ATTR_OPTION: "Couch"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "failed_communication"
