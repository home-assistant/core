"""Tests for the MotionMount Number platform."""

import socket
from unittest.mock import MagicMock

import motionmount
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

EXTENSION_ENTITY_ID = "number.my_motionmount_extension"
TURN_ENTITY_ID = "number.my_motionmount_turn"


@pytest.mark.parametrize(
    ("entity_id", "value", "method", "expected"),
    [
        pytest.param(EXTENSION_ENTITY_ID, 42, "set_extension", 42, id="extension"),
        pytest.param(TURN_ENTITY_ID, 42, "set_turn", -42, id="turn"),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount: MagicMock,
    entity_id: str,
    value: int,
    method: str,
    expected: int,
) -> None:
    """Test setting a value."""
    mock_motionmount.is_authenticated = True
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    getattr(mock_motionmount, method).assert_awaited_once_with(expected)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        pytest.param(EXTENSION_ENTITY_ID, "set_extension", id="extension"),
        pytest.param(TURN_ENTITY_ID, "set_turn", id="turn"),
    ],
)
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ConnectionResetError, id="connection_reset"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(socket.gaierror, id="gaierror"),
        pytest.param(motionmount.NotConnectedError, id="not_connected"),
    ],
)
async def test_set_value_communication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount: MagicMock,
    entity_id: str,
    method: str,
    exception: type[Exception],
) -> None:
    """Test a communication error while setting a value raises HomeAssistantError."""
    mock_motionmount.is_authenticated = True
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    getattr(mock_motionmount, method).side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 42},
            blocking=True,
        )

    assert exc_info.value.translation_key == "failed_communication"
