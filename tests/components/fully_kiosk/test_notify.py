"""Test the Fully Kiosk Browser notify platform."""

from unittest.mock import MagicMock

from fullykiosk import FullyKioskError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


async def test_notify_text_to_speech(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test notify text to speech entity."""
    message = "one, two, testing, testing"
    await hass.services.async_call(
        "notify",
        "send_message",
        {
            "entity_id": "notify.amazon_fire_text_to_speech",
            "message": message,
        },
        blocking=True,
    )
    mock_fully_kiosk.sendCommand.assert_called_with("textToSpeech", text=message)


async def test_notify_text_to_speech_raises(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test notify text to speech entity raises."""
    mock_fully_kiosk.sendCommand.side_effect = FullyKioskError("error", "status")
    message = "one, two, testing, testing"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "notify",
            "send_message",
            {
                "entity_id": "notify.amazon_fire_text_to_speech",
                "message": message,
            },
            blocking=True,
        )
    mock_fully_kiosk.sendCommand.assert_called_with("textToSpeech", text=message)


async def test_notify_overlay_message(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test notify overlay message entity."""
    message = "one, two, testing, testing"
    await hass.services.async_call(
        "notify",
        "send_message",
        {
            "entity_id": "notify.amazon_fire_overlay_message",
            "message": message,
        },
        blocking=True,
    )
    mock_fully_kiosk.sendCommand.assert_called_with("setOverlayMessage", text=message)
