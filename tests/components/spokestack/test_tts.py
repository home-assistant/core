"""Tests for Spokestack TTS Integration."""
import os
import shutil
from unittest.mock import patch

import pytest
from spokestack.tts.clients.spokestack import TTSError

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.spokestack.const import (
    CONF_IDENTITY,
    CONF_SECRET_KEY,
    DEFAULT_MODE,
    DEFAULT_PROFILE,
    DEFAULT_VOICE,
)
import homeassistant.components.tts as tts
from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


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
def mock_client():
    """Mock TextToSpeechClient."""
    with patch(
        "homeassistant.components.spokestack.tts.TextToSpeechClient"
    ) as mock_client:
        yield mock_client


async def test_service_say_default(hass, mock_client, calls):
    """Test service call say."""
    await async_setup_component(
        hass,
        tts.DOMAIN,
        {
            tts.DOMAIN: {
                "platform": "spokestack",
                CONF_IDENTITY: "test_key",
                CONF_SECRET_KEY: "test_secret",
            }
        },
    )
    await hass.services.async_call(
        tts.DOMAIN,
        "spokestack_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    assert len(mock_client.mock_calls) == 3
    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".mp3") != -1

    # Confirm validation call is made.
    assert mock_client.mock_calls[0][2] == {
        "key_id": "test_key",
        "key_secret": "test_secret",
    }
    # Confirm synthesize is called with valid arguments.
    assert mock_client.mock_calls[1][2] == {
        "utterance": "There is a person at the front door.",
        "voice": DEFAULT_VOICE,
        "mode": DEFAULT_MODE,
        "profile": DEFAULT_PROFILE,
    }


async def test_service_say_ssml(hass, mock_client, calls):
    """Test service call say."""
    await async_setup_component(
        hass,
        tts.DOMAIN,
        {
            tts.DOMAIN: {
                "platform": "spokestack",
                CONF_IDENTITY: "test_key",
                CONF_SECRET_KEY: "test_secret",
            }
        },
    )
    await hass.services.async_call(
        tts.DOMAIN,
        "spokestack_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {"mode": "ssml"},
        },
        blocking=True,
    )
    assert len(calls) == 1
    assert len(mock_client.mock_calls) == 3
    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".mp3") != -1

    # Confirm validation call is made.
    assert mock_client.mock_calls[0][2] == {
        "key_id": "test_key",
        "key_secret": "test_secret",
    }
    # Confirm synthesize is called with valid arguments.
    assert mock_client.mock_calls[1][2] == {
        "utterance": "There is a person at the front door.",
        "voice": DEFAULT_VOICE,
        "mode": "ssml",
        "profile": DEFAULT_PROFILE,
    }


async def test_service_say_error(hass, mock_client, calls):
    """Test service call say with http response 400."""
    mock_client.synthesize.return_value = TTSError

    await async_setup_component(
        hass,
        tts.DOMAIN,
        {
            tts.DOMAIN: {
                "platform": "spokestack",
                CONF_IDENTITY: "test_key",
                CONF_SECRET_KEY: "test_secret",
            }
        },
    )
    await hass.services.async_call(
        tts.DOMAIN,
        "spokestack_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )
    # 1 call due to the validate call
    assert len(calls) == 1
