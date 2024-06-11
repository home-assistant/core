"""Test the Fully Kiosk notify platform."""

from unittest.mock import MagicMock

from homeassistant.components.notify import ATTR_MESSAGE, DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_notify(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test standard Fully Kiosk binary sensors."""
    message = "one, two, testing, testing"
    service = "fully_kiosk_192_168_1_234"
    assert hass.services.has_service(NOTIFY_DOMAIN, service)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        service,
        {ATTR_MESSAGE: message},
        blocking=True,
    )
    mock_fully_kiosk.sendCommand.assert_called_with("textToSpeech", text=message)
