"""Tests for cloud tts."""
from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import MagicMock, Mock

from hass_nabucasa import voice
import pytest
import voluptuous as vol

from homeassistant.components.cloud import DOMAIN, const, tts
from homeassistant.components.tts import DOMAIN as TTS_DOMAIN
from homeassistant.components.tts.helper import get_engine_instance
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def cloud_with_prefs(cloud_prefs):
    """Return a cloud mock with prefs."""
    return Mock(client=Mock(prefs=cloud_prefs))


def test_default_exists() -> None:
    """Test our default language exists."""
    assert const.DEFAULT_TTS_DEFAULT_VOICE in voice.MAP_VOICE


def test_schema() -> None:
    """Test schema."""
    assert "nl-NL" in tts.SUPPORT_LANGUAGES

    processed = tts.PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL"})
    assert processed["gender"] == "female"

    with pytest.raises(vol.Invalid):
        tts.PLATFORM_SCHEMA(
            {"platform": "cloud", "language": "non-existing", "gender": "female"}
        )

    with pytest.raises(vol.Invalid):
        tts.PLATFORM_SCHEMA(
            {"platform": "cloud", "language": "nl-NL", "gender": "not-supported"}
        )

    # Should not raise
    tts.PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL", "gender": "female"})
    tts.PLATFORM_SCHEMA({"platform": "cloud"})


@pytest.mark.parametrize(
    ("engine_id", "platform_config"),
    [
        (
            DOMAIN,
            None,
        ),
        (
            DOMAIN,
            {
                "platform": DOMAIN,
                "service_name": "yaml",
                "language": "fr-FR",
                "gender": "female",
            },
        ),
    ],
)
async def test_prefs_default_voice(
    hass: HomeAssistant,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    engine_id: str,
    platform_config: dict[str, Any] | None,
) -> None:
    """Test cloud provider uses the preferences."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, TTS_DOMAIN, {TTS_DOMAIN: platform_config})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert cloud.client.prefs.tts_default_voice == ("en-US", "female")

    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()

    engine = get_engine_instance(hass, engine_id)

    assert engine is not None
    # The platform config provider will be overridden by the discovery info provider.
    assert engine.default_language == "en-US"
    assert engine.default_options == {"gender": "female", "audio_output": "mp3"}

    await set_cloud_prefs({"tts_default_voice": ("nl-NL", "male")})
    await hass.async_block_till_done()

    assert engine.default_language == "nl-NL"
    assert engine.default_options == {"gender": "male", "audio_output": "mp3"}


async def test_provider_properties(
    hass: HomeAssistant,
    cloud: MagicMock,
) -> None:
    """Test cloud provider."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()

    engine = get_engine_instance(hass, DOMAIN)

    assert engine is not None
    assert engine.supported_options == ["gender", "voice", "audio_output"]
    assert "nl-NL" in engine.supported_languages
    supported_voices = engine.async_get_supported_voices("nl-NL")
    assert supported_voices is not None
    assert tts.Voice("ColetteNeural", "ColetteNeural") in supported_voices


async def test_get_tts_audio(cloud_with_prefs) -> None:
    """Test cloud provider."""
    tts_info = {"platform_loaded": Mock()}
    provider = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}), None, tts_info
    )
    assert provider.supported_options == ["gender", "voice", "audio_output"]
    assert "nl-NL" in provider.supported_languages
