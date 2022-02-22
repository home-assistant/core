"""The tests for the VoiceRSS speech platform."""
import asyncio
from http import HTTPStatus
import os
import shutil

import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service
from tests.components.tts.conftest import mutagen_mock  # noqa: F401

URL = "https://api.voicerss.org/"
FORM_DATA = {
    "key": "1234567xx",
    "hl": "en-us",
    "c": "MP3",
    "f": "8khz_8bit_mono",
    "src": "I person is on front of your door.",
}


@pytest.fixture(autouse=True)
def cleanup_cache(hass):
    """Prevent TTS writing."""
    yield
    default_tts = hass.config.path(tts.DEFAULT_CACHE_DIR)
    if os.path.isdir(default_tts):
        shutil.rmtree(default_tts)


async def test_setup_component(hass):
    """Test setup component."""
    config = {tts.DOMAIN: {"platform": "voicerss", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_component_without_api_key(hass):
    """Test setup component without api key."""
    config = {tts.DOMAIN: {"platform": "voicerss"}}

    with assert_setup_component(0, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_service_say(hass, aioclient_mock):
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    aioclient_mock.post(URL, data=FORM_DATA, status=HTTPStatus.OK, content=b"test")

    config = {tts.DOMAIN: {"platform": "voicerss", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "voicerss_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA
    assert calls[0].data[ATTR_MEDIA_CONTENT_ID].find(".mp3") != -1


async def test_service_say_german_config(hass, aioclient_mock):
    """Test service call say with german code in the config."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    form_data = {**FORM_DATA, "hl": "de-de"}
    aioclient_mock.post(URL, data=form_data, status=HTTPStatus.OK, content=b"test")

    config = {
        tts.DOMAIN: {
            "platform": "voicerss",
            "api_key": "1234567xx",
            "language": "de-de",
        }
    }

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "voicerss_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == form_data


async def test_service_say_german_service(hass, aioclient_mock):
    """Test service call say with german code in the service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    form_data = {**FORM_DATA, "hl": "de-de"}
    aioclient_mock.post(URL, data=form_data, status=HTTPStatus.OK, content=b"test")

    config = {tts.DOMAIN: {"platform": "voicerss", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "voicerss_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "I person is on front of your door.",
            tts.ATTR_LANGUAGE: "de-de",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == form_data


async def test_service_say_error(hass, aioclient_mock):
    """Test service call say with http response 400."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    aioclient_mock.post(URL, data=FORM_DATA, status=400, content=b"test")

    config = {tts.DOMAIN: {"platform": "voicerss", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "voicerss_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 0
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA


async def test_service_say_timeout(hass, aioclient_mock):
    """Test service call say with http timeout."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    aioclient_mock.post(URL, data=FORM_DATA, exc=asyncio.TimeoutError())

    config = {tts.DOMAIN: {"platform": "voicerss", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "voicerss_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 0
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA


async def test_service_say_error_msg(hass, aioclient_mock):
    """Test service call say with http error api message."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    aioclient_mock.post(
        URL,
        data=FORM_DATA,
        status=HTTPStatus.OK,
        content=b"The subscription does not support SSML!",
    )

    config = {tts.DOMAIN: {"platform": "voicerss", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "voicerss_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "I person is on front of your door.",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 0
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA
