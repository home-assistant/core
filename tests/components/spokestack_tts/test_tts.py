"""Tests for Spokestack TTS Integration."""
import asyncio
import os
import shutil
from unittest.mock import patch

import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    MEDIA_TYPE_MUSIC,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.spokestack_tts.tts import TTSError
import homeassistant.components.tts as tts
from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant, mock_service


@pytest.fixture(autouse=True)
def cleanup_cache(hass):
    """Clean up TTS cache."""
    yield
    default_tts = hass.config.path(tts.DEFAULT_CACHE_DIR)
    if os.path.isdir(default_tts):
        shutil.rmtree(default_tts)


def test_service_say():
    """Test service call say."""
    hass = get_test_home_assistant()

    asyncio.run_coroutine_threadsafe(
        async_process_ha_core_config(
            hass, {"internal_url": "http://example.local:8123"}
        ),
        hass.loop,
    )

    calls = mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)
    config = {
        tts.DOMAIN: {
            "platform": "spokestack_tts",
            "key_id": "mock key",
            "key_secret": "mock_secret",
        }
    }

    with assert_setup_component(1, tts.DOMAIN):
        setup_component(hass, tts.DOMAIN, config)

    with patch(
        "homeassistant.components.spokestack_tts.tts.TextToSpeechClient.synthesize",
        return_value=[b"audio"],
    ) as mock_client:

        hass.services.call(
            tts.DOMAIN,
            "spokestack_tts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "Welcome to Home Assistant.",
            },
            blocking=True,
        )
    mock_client.assert_called()
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find("mp3")

    hass.stop()


def test_with_error():
    """Test service with error."""
    hass = get_test_home_assistant()

    asyncio.run_coroutine_threadsafe(
        async_process_ha_core_config(
            hass, {"internal_url": "http://example.local:8123"}
        ),
        hass.loop,
    )

    _ = mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)
    config = {
        tts.DOMAIN: {
            "platform": "spokestack_tts",
            "key_id": "mock key",
            "key_secret": "mock_secret",
        }
    }

    with assert_setup_component(1, tts.DOMAIN):
        setup_component(hass, tts.DOMAIN, config)

    with patch(
        "homeassistant.components.spokestack_tts.tts.TextToSpeechClient.synthesize",
        side_effect=TTSError([{"message": "mock error"}]),
    ):

        hass.services.call(
            tts.DOMAIN,
            "spokestack_tts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "Welcome to Home Assistant.",
            },
            blocking=True,
        )
    hass.stop()
