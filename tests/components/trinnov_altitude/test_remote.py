"""Tests for Trinnov Altitude remote platform."""

from unittest.mock import MagicMock

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
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
    assert mock_device.leave_standby.call_count == 1
