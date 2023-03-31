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

    provider_pref = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}), None, {}
    )
    provider_conf = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}),
        {"language": "fr-FR", "gender": "female"},
        None,
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


async def test_provider_properties(cloud_with_prefs) -> None:
    """Test cloud provider."""
    provider = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}), None, {}
    )
    assert provider.supported_options == ["gender"]
    assert "nl-NL" in provider.supported_languages


async def test_get_tts_audio(cloud_with_prefs) -> None:
    """Test cloud provider."""
    provider = await tts.async_get_engine(
        Mock(data={const.DOMAIN: cloud_with_prefs}), None, {}
    )
    assert provider.supported_options == ["gender"]
    assert "nl-NL" in provider.supported_languages
