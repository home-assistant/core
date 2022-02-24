"""The tests for the Yandex SpeechKit speech platform."""
import asyncio
from http import HTTPStatus
import os
import shutil

import pytest

from homeassistant.components.media_player.const import (
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service
from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    mutagen_mock,
)

URL = "https://tts.voicetech.yandex.net/generate?"


@pytest.fixture(autouse=True)
def cleanup_cache(hass):
    """Prevent TTS writing."""
    yield
    default_tts = hass.config.path(tts.DEFAULT_CACHE_DIR)
    if os.path.isdir(default_tts):
        shutil.rmtree(default_tts)


async def test_setup_component(hass):
    """Test setup component."""
    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_component_without_api_key(hass):
    """Test setup component without api key."""
    config = {tts.DOMAIN: {"platform": "yandextts"}}

    with assert_setup_component(0, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_service_say(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "neutral",
        "speed": 1,
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)

    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1


async def test_service_say_russian_config(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "ru-RU",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "neutral",
        "speed": 1,
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)

    config = {
        tts.DOMAIN: {
            "platform": "yandextts",
            "api_key": "1234567xx",
            "language": "ru-RU",
        }
    }

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1


async def test_service_say_russian_service(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "ru-RU",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "neutral",
        "speed": 1,
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)

    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "HomeAssistant",
            tts.ATTR_LANGUAGE: "ru-RU",
        },
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1


async def test_service_say_timeout(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "neutral",
        "speed": 1,
    }
    aioclient_mock.get(
        URL,
        status=HTTPStatus.OK,
        exc=asyncio.TimeoutError(),
        params=url_param,
    )

    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0
    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_http_error(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "neutral",
        "speed": 1,
    }
    aioclient_mock.get(
        URL,
        status=HTTPStatus.FORBIDDEN,
        content=b"test",
        params=url_param,
    )

    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_service_say_specified_speaker(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "alyss",
        "format": "mp3",
        "emotion": "neutral",
        "speed": 1,
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)

    config = {
        tts.DOMAIN: {
            "platform": "yandextts",
            "api_key": "1234567xx",
            "voice": "alyss",
        }
    }

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1


async def test_service_say_specified_emotion(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "evil",
        "speed": 1,
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)

    config = {
        tts.DOMAIN: {
            "platform": "yandextts",
            "api_key": "1234567xx",
            "emotion": "evil",
        }
    }

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1


async def test_service_say_specified_low_speed(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "neutral",
        "speed": "0.1",
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)

    config = {
        tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx", "speed": 0.1}
    }

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1


async def test_service_say_specified_speed(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "neutral",
        "speed": 2,
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)

    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx", "speed": 2}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {"entity_id": "media_player.something", tts.ATTR_MESSAGE: "HomeAssistant"},
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1


async def test_service_say_specified_options(hass, aioclient_mock):
    """Test service call say with options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    url_param = {
        "text": "HomeAssistant",
        "lang": "en-US",
        "key": "1234567xx",
        "speaker": "zahar",
        "format": "mp3",
        "emotion": "evil",
        "speed": 2,
    }
    aioclient_mock.get(URL, status=HTTPStatus.OK, content=b"test", params=url_param)
    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "yandextts_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "HomeAssistant",
            "options": {"emotion": "evil", "speed": 2},
        },
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(calls) == 1
