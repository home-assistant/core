"""Test the legacy tts setup."""
from __future__ import annotations

import pytest

from homeassistant.components.tts import Provider
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .common import MockTTS

from tests.common import MockModule, mock_integration, mock_platform


async def test_invalid_platform(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test platform setup with an invalid platform."""
    await async_load_platform(
        hass,
        "tts",
        "bad_tts",
        {"tts": [{"platform": "bad_tts"}]},
        hass_config={"tts": [{"platform": "bad_tts"}]},
    )
    await hass.async_block_till_done()

    assert "Unknown text to speech platform specified" in caplog.text


async def test_platform_setup_with_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test platform setup with an error during setup."""

    class BadPlatform(MockTTS):
        """A mock TTS platform with a setup error."""

        async def async_get_engine(
            self,
            hass: HomeAssistant,
            config: ConfigType,
            discovery_info: DiscoveryInfoType | None = None,
        ) -> Provider:
            """Raise exception during platform setup."""
            raise Exception("Setup error")  # pylint: disable=broad-exception-raised

    mock_integration(hass, MockModule(domain="bad_tts"))
    mock_platform(hass, "bad_tts.tts", BadPlatform())

    await async_load_platform(
        hass,
        "tts",
        "bad_tts",
        {},
        hass_config={"tts": [{"platform": "bad_tts"}]},
    )
    await hass.async_block_till_done()

    assert "Error setting up platform: bad_tts" in caplog.text
