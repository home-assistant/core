"""The tests for the Google speech platform."""
import os
import shutil
from unittest.mock import patch

from gtts import gTTSError
import pytest

from homeassistant.components import media_source, tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service
from tests.components.tts.conftest import mutagen_mock  # noqa: F401


async def get_media_source_url(hass, media_content_id):
    """Get the media source url."""
    if media_source.DOMAIN not in hass.config.components:
        assert await async_setup_component(hass, media_source.DOMAIN, {})

    resolved = await media_source.async_resolve_media(hass, media_content_id, None)
    return resolved.url


@pytest.fixture(autouse=True)
def cleanup_cache(hass):
    """Clean up TTS cache."""
    yield
    default_tts = hass.config.path(tts.DEFAULT_CACHE_DIR)
    if os.path.isdir(default_tts):
        shutil.rmtree(default_tts)


@pytest.fixture
async def calls(hass):
    """Mock media player calls."""
    return async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)


@pytest.fixture(autouse=True)
async def setup_internal_url(hass):
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
def mock_gtts():
    """Mock gtts."""
    with patch("homeassistant.components.google_translate.tts.gTTS") as mock_gtts:
        yield mock_gtts


async def test_service_say(hass: HomeAssistant, mock_gtts, calls) -> None:
    """Test service call say."""

    await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {"platform": "google_translate"}}
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "google_translate_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(mock_gtts.mock_calls) == 2
    assert url.endswith(".mp3")

    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "com",
    }


async def test_service_say_german_config(hass: HomeAssistant, mock_gtts, calls) -> None:
    """Test service call say with german code in the config."""

    await async_setup_component(
        hass,
        tts.DOMAIN,
        {tts.DOMAIN: {"platform": "google_translate", "language": "de"}},
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "google_translate_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "de",
        "tld": "com",
    }


async def test_service_say_german_service(
    hass: HomeAssistant, mock_gtts, calls
) -> None:
    """Test service call say with german code in the service."""

    config = {
        tts.DOMAIN: {"platform": "google_translate", "service_name": "google_say"}
    }

    await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "google_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_LANGUAGE: "de",
        },
        blocking=True,
    )

    assert len(calls) == 1
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "de",
        "tld": "com",
    }


async def test_service_say_en_uk_config(hass: HomeAssistant, mock_gtts, calls) -> None:
    """Test service call say with en-uk code in the config."""

    await async_setup_component(
        hass,
        tts.DOMAIN,
        {tts.DOMAIN: {"platform": "google_translate", "language": "en-uk"}},
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "google_translate_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "co.uk",
    }


async def test_service_say_en_uk_service(hass: HomeAssistant, mock_gtts, calls) -> None:
    """Test service call say with en-uk code in the config."""

    await async_setup_component(
        hass,
        tts.DOMAIN,
        {tts.DOMAIN: {"platform": "google_translate"}},
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "google_translate_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_LANGUAGE: "en-uk",
        },
        blocking=True,
    )

    assert len(calls) == 1
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(mock_gtts.mock_calls) == 2
    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "co.uk",
    }


async def test_service_say_en_couk(hass: HomeAssistant, mock_gtts, calls) -> None:
    """Test service call say in co.uk tld accent."""

    await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {"platform": "google_translate"}}
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "google_translate_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {"tld": "co.uk"},
        },
        blocking=True,
    )

    assert len(calls) == 1
    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(mock_gtts.mock_calls) == 2
    assert url.endswith(".mp3")

    assert mock_gtts.mock_calls[0][2] == {
        "text": "There is a person at the front door.",
        "lang": "en",
        "tld": "co.uk",
    }


async def test_service_say_error(hass: HomeAssistant, mock_gtts, calls) -> None:
    """Test service call say with http response 400."""
    mock_gtts.return_value.write_to_fp.side_effect = gTTSError
    await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {"platform": "google_translate"}}
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "google_translate_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    with pytest.raises(HomeAssistantError):
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(mock_gtts.mock_calls) == 2
