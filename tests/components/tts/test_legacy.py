"""Test the legacy tts setup."""

from __future__ import annotations

import pytest

from homeassistant.components.media_player import (
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.tts import ATTR_MESSAGE, DOMAIN, Provider
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component

from .common import SUPPORT_LANGUAGES, MockProvider, MockTTS

from tests.common import (
    MockModule,
    assert_setup_component,
    async_mock_service,
    mock_integration,
    mock_platform,
)


class DefaultProvider(Provider):
    """Test provider."""

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORT_LANGUAGES


async def test_default_provider_attributes() -> None:
    """Test default provider attributes."""
    provider = DefaultProvider()

    assert provider.hass is None
    assert provider.name is None
    assert provider.default_language is None
    assert provider.supported_languages == SUPPORT_LANGUAGES
    assert provider.supported_options is None
    assert provider.default_options is None
    assert provider.async_get_supported_voices("test") is None


async def test_deprecated_platform(hass: HomeAssistant) -> None:
    """Test deprecated google platform."""
    with assert_setup_component(0, DOMAIN):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"platform": "google"}}
        )


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

    assert "Unknown text-to-speech platform specified" in caplog.text


async def test_platform_setup_without_provider(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_provider: MockProvider
) -> None:
    """Test platform setup without provider returned."""

    class BadPlatform(MockTTS):
        """A mock TTS platform without provider."""

        async def async_get_engine(
            self,
            hass: HomeAssistant,
            config: ConfigType,
            discovery_info: DiscoveryInfoType | None = None,
        ) -> Provider | None:
            """Raise exception during platform setup."""
            return None

    mock_integration(hass, MockModule(domain="bad_tts"))
    mock_platform(hass, "bad_tts.tts", BadPlatform(mock_provider))

    await async_load_platform(
        hass,
        "tts",
        "bad_tts",
        {},
        hass_config={"tts": [{"platform": "bad_tts"}]},
    )
    await hass.async_block_till_done()

    assert "Error setting up platform: bad_tts" in caplog.text


async def test_platform_setup_with_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_provider: MockProvider,
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
    mock_platform(hass, "bad_tts.tts", BadPlatform(mock_provider))

    await async_load_platform(
        hass,
        "tts",
        "bad_tts",
        {},
        hass_config={"tts": [{"platform": "bad_tts"}]},
    )
    await hass.async_block_till_done()

    assert "Error setting up platform: bad_tts" in caplog.text


async def test_service_without_cache_config(
    hass: HomeAssistant, mock_tts_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {DOMAIN: {"platform": "test", "cache": False}}

    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "test_say",
        {
            ATTR_ENTITY_ID: "media_player.something",
            ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert not (
        mock_tts_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_test.mp3"
    ).is_file()
