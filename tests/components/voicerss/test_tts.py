"""The tests for the VoiceRSS speech platform."""
import asyncio
from http import HTTPStatus

import pytest

from homeassistant.components import media_source, tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service
from tests.test_util.aiohttp import AiohttpClientMocker

URL = "https://api.voicerss.org/"
FORM_DATA = {
    "key": "1234567xx",
    "hl": "en-us",
    "c": "MP3",
    "f": "8khz_8bit_mono",
    "src": "I person is on front of your door.",
}


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock):
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir):
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


async def get_media_source_url(hass, media_content_id):
    """Get the media source url."""
    if media_source.DOMAIN not in hass.config.components:
        assert await async_setup_component(hass, media_source.DOMAIN, {})

    resolved = await media_source.async_resolve_media(hass, media_content_id, None)
    return resolved.url


async def test_setup_component(hass: HomeAssistant) -> None:
    """Test setup component."""
    config = {tts.DOMAIN: {"platform": "voicerss", "api_key": "1234567xx"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_component_without_api_key(hass: HomeAssistant) -> None:
    """Test setup component without api key."""
    config = {tts.DOMAIN: {"platform": "voicerss"}}

    with assert_setup_component(0, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_service_say(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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
    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert url.endswith(".mp3")
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA


async def test_service_say_german_config(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == form_data


async def test_service_say_german_service(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == form_data


async def test_service_say_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    with pytest.raises(HomeAssistantError):
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA


async def test_service_say_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    with pytest.raises(HomeAssistantError):
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA


async def test_service_say_error_msg(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    with pytest.raises(media_source.Unresolvable):
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == FORM_DATA
