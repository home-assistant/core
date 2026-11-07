"""Tests for the Telldus Live cover platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.tellduslive.const import UP
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

COVER = "cover.kitchen"


@pytest.fixture
def device(mock_tellduslive: MagicMock) -> MagicMock:
    """Return a mocked device that is a cover."""
    device = mock_tellduslive.devices[0]
    device.methods = UP
    device.is_down = True
    return device


@pytest.mark.usefixtures("setup_integration")
async def test_cover_state(hass: HomeAssistant) -> None:
    """Test the cover state follows the device."""
    assert hass.states.get(COVER).state == STATE_CLOSED


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_OPEN_COVER, "up"),
        (SERVICE_CLOSE_COVER, "down"),
        (SERVICE_STOP_COVER, "stop"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_cover_commands(
    hass: HomeAssistant, device: MagicMock, service: str, method: str
) -> None:
    """Test cover services send the matching command."""
    await hass.services.async_call(
        COVER_DOMAIN, service, {ATTR_ENTITY_ID: COVER}, blocking=True
    )

    getattr(device, method).assert_called_once_with()


@pytest.mark.usefixtures("setup_integration")
async def test_cover_command_rejected(hass: HomeAssistant, device: MagicMock) -> None:
    """Test a rejected command raises."""
    device.up.return_value = False

    with pytest.raises(HomeAssistantError, match="did not accept the command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER}, blocking=True
        )
