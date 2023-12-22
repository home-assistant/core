"""Tests for cloud tts."""
from unittest.mock import Mock

from hass_nabucasa import voice
import pytest
import voluptuous as vol

from homeassistant.components.cloud import const, tts
from homeassistant.core import HomeAssistant


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


async def test_prefs_default_voice(
    hass: HomeAssistant, cloud_with_prefs, cloud_prefs
) -> None:
    """Test cloud provider uses the preferences."""
    assert cloud_prefs.tts_default_voice == ("en-US", "female")

    tts_info = {"platform_loaded": Mock()}
    provider_pref = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}), None, tts_info
    )
    provider_conf = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}),
        {"language": "fr-FR", "gender": "female"},
        None,
    )

    assert provider_pref.default_language == "en-US"
    assert provider_pref.default_options == {"gender": "female", "audio_output": "mp3"}
    assert provider_conf.default_language == "fr-FR"
    assert provider_conf.default_options == {"gender": "female", "audio_output": "mp3"}

    await cloud_prefs.async_update(tts_default_voice=("nl-NL", "male"))
    await hass.async_block_till_done()

    assert provider_pref.default_language == "nl-NL"
    assert provider_pref.default_options == {"gender": "male", "audio_output": "mp3"}
    assert provider_conf.default_language == "fr-FR"
    assert provider_conf.default_options == {"gender": "female", "audio_output": "mp3"}


async def test_provider_properties(cloud_with_prefs) -> None:
    """Test cloud provider."""
    tts_info = {"platform_loaded": Mock()}
    provider = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}), None, tts_info
    )
    assert provider.supported_options == ["gender", "voice", "audio_output"]
    assert "nl-NL" in provider.supported_languages
    assert tts.Voice(
        "ColetteNeural", "ColetteNeural"
    ) in provider.async_get_supported_voices("nl-NL")


async def test_get_tts_audio(cloud_with_prefs) -> None:
    """Test cloud provider."""
    tts_info = {"platform_loaded": Mock()}
    provider = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}), None, tts_info
    )
    assert provider.supported_options == ["gender", "voice", "audio_output"]
    assert "nl-NL" in provider.supported_languages
