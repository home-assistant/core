"""Tests for cloud tts."""
from unittest.mock import Mock

from hass_nabucasa import voice

from homeassistant.components.cloud import const, tts


def test_default_exists():
    """Test our default language exists."""
    assert const.DEFAULT_TTS_DEFAULT_VOICE in voice.MAP_VOICE


def test_schema():
    """Test schema."""
    assert "nl-NL" in tts.SUPPORT_LANGUAGES

    processed = tts.PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL"})
    assert processed["gender"] == "female"

    # Should not raise
    processed = tts.PLATFORM_SCHEMA(
        {"platform": "cloud", "language": "nl-NL", "gender": "female"}
    )


async def test_prefs_default_voice(hass, cloud_prefs):
    """Test cloud provider uses the preferences."""
    assert cloud_prefs.tts_default_voice == ("en-US", "female")

    provider_pref = tts.CloudProvider(Mock(client=Mock(prefs=cloud_prefs)), None, None)
    provider_conf = tts.CloudProvider(
        Mock(client=Mock(prefs=cloud_prefs)), "fr-FR", "female"
    )

    assert provider_pref.default_language == "en-US"
    assert provider_pref.default_options == {"gender": "female"}
    assert provider_conf.default_language == "fr-FR"
    assert provider_conf.default_options == {"gender": "female"}

    await cloud_prefs.async_update(tts_default_voice=("nl-NL", "male"))
    await hass.async_block_till_done()

    assert provider_pref.default_language == "nl-NL"
    assert provider_pref.default_options == {"gender": "male"}
    assert provider_conf.default_language == "fr-FR"
    assert provider_conf.default_options == {"gender": "female"}
