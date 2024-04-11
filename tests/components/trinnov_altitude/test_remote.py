"""Tests for Trinnov Altitude remote platform."""

from unittest.mock import MagicMock

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from . import MOCK_ID

from tests.common import MockConfigEntry

ENTITY_ID = f"remote.trinnov_altitude_{MOCK_ID}"


async def test_entity(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test entity attributes."""

    assert hass.states.get(ENTITY_ID)


async def test_commands(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test service calls."""

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.power_on.call_count == 1

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert mock_device.power_off.call_count == 1

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["source_set 1"]},
        blocking=True,
    )
    mock_device.source_set.assert_called_once_with(1)

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["volume_down"]},
        blocking=True,
    )
    assert mock_device.volume_down.call_count == 1

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["volume_ramp -42.5 10"]},
        blocking=True,
    )
    mock_device.volume_ramp.assert_called_once_with(-42.5, 10)

    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["volume_set -40.5"]},
        blocking=True,
    )
    mock_device.volume_set.assert_called_once_with(-40.5)
