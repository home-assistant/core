"""The tests for the Google Assistant SDK TTS platform."""
import os
import shutil
from unittest.mock import patch

import pytest

from homeassistant.components import media_source, tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup

from tests.common import async_mock_service


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
async def media_player_calls(hass):
    """Mock media player calls."""
    return async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)


@pytest.fixture(autouse=True)
async def setup_internal_url(hass):
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
def mock_text_assistant():
    """Mock gtts."""
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist",
        return_value=["text_response", None, b"audio_response"],
    ) as mock_text_assistant:
        yield mock_text_assistant


async def test_service_say(
    hass, mock_text_assistant, media_player_calls, setup_integration: ComponentSetup
):
    """Test service call say."""
    await setup_integration()

    await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {"platform": "google_assistant_sdk"}}
    )

    message = "tell me a joke"
    await hass.services.async_call(
        tts.DOMAIN,
        "google_assistant_sdk_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: message,
        },
        blocking=True,
    )

    assert len(media_player_calls) == 1
    url = await get_media_source_url(
        hass, media_player_calls[0].data[ATTR_MEDIA_CONTENT_ID]
    )
    assert url.endswith(".mp3")
    mock_text_assistant.assert_called_once_with(message)
