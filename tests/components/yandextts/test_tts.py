"""The tests for the Yandex SpeechKit speech platform."""
from http import HTTPStatus

import pytest

from homeassistant.components import tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service
from tests.components.tts.common import retrieve_media
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

URL = "https://tts.voicetech.yandex.net/generate?"


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock):
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir):
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


async def test_setup_component(hass: HomeAssistant) -> None:
    """Test setup component."""
    config = {tts.DOMAIN: {"platform": "yandextts", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_component_without_api_key(hass: HomeAssistant) -> None:
    """Test setup component without api key."""
    config = {tts.DOMAIN: {"platform": "yandextts"}}

    with assert_setup_component(0, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_service_say(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_russian_config(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_russian_service(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_timeout(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        exc=TimeoutError(),
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
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.NOT_FOUND
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_http_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.NOT_FOUND
    )


async def test_service_say_specified_speaker(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_specified_emotion(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_specified_low_speed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_specified_speed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_say_specified_options(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
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
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(aioclient_mock.mock_calls) == 1
