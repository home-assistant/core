"""The tests for the MaryTTS speech platform."""

from http import HTTPStatus
import io
from unittest.mock import patch
import wave

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
from tests.typing import ClientSessionGenerator


def get_empty_wav() -> bytes:
    """Get bytes for empty WAV file."""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setframerate(22050)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)

        return wav_io.getvalue()


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir):
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


async def test_setup_component(hass: HomeAssistant) -> None:
    """Test setup component."""
    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_service_say(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        return_value=get_empty_wav(),
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

        assert (
            await retrieve_media(
                hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID]
            )
            == HTTPStatus.OK
        )

    mock_speak.assert_called_once()
    mock_speak.assert_called_with("HomeAssistant", {})

    assert len(calls) == 1


async def test_service_say_with_effect(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test service call say with effects."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts", "effect": {"Volume": "amount:2.0;"}}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        return_value=get_empty_wav(),
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

        assert (
            await retrieve_media(
                hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID]
            )
            == HTTPStatus.OK
        )

    mock_speak.assert_called_once()
    mock_speak.assert_called_with("HomeAssistant", {"Volume": "amount:2.0;"})

    assert len(calls) == 1


async def test_service_say_http_error(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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

        assert (
            await retrieve_media(
                hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID]
            )
            == HTTPStatus.NOT_FOUND
        )

    mock_speak.assert_called_once()
