"""The tests for the MaryTTS speech platform."""
import os
import shutil
from unittest.mock import patch

import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service


@pytest.fixture(autouse=True)
def cleanup_cache(hass):
    """Prevent TTS writing."""
    yield
    default_tts = hass.config.path(tts.DEFAULT_CACHE_DIR)
    if os.path.isdir(default_tts):
        shutil.rmtree(default_tts)


async def test_setup_component(hass):
    """Test setup component."""
    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_service_say(hass):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        return_value=b"audio",
    ) as mock_speak:
        await hass.services.async_call(
            tts.DOMAIN,
            "marytts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "HomeAssistant",
            },
            blocking=True,
        )

    mock_speak.assert_called_once()
    mock_speak.assert_called_with("HomeAssistant", {})

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1


async def test_service_say_with_effect(hass):
    """Test service call say with effects."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts", "effect": {"Volume": "amount:2.0;"}}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        return_value=b"audio",
    ) as mock_speak:
        await hass.services.async_call(
            tts.DOMAIN,
            "marytts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "HomeAssistant",
            },
            blocking=True,
        )

    mock_speak.assert_called_once()
    mock_speak.assert_called_with("HomeAssistant", {"Volume": "amount:2.0;"})

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".wav") != -1


async def test_service_say_http_error(hass):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        side_effect=Exception(),
    ) as mock_speak:
        await hass.services.async_call(
            tts.DOMAIN,
            "marytts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "HomeAssistant",
            },
        )
        await hass.async_block_till_done()

    mock_speak.assert_called_once()
    assert len(calls) == 0
