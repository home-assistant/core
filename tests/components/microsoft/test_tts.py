"""Tests for Microsoft text-to-speech."""

from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from pycsspeechtts import pycsspeechtts
import pytest

from homeassistant.components import tts
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID
from homeassistant.components.microsoft.tts import SUPPORTED_LANGUAGES
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import ServiceNotFound
from homeassistant.setup import async_setup_component

from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant):
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
def mock_tts():
    """Mock tts."""
    with patch(
        "homeassistant.components.microsoft.tts.pycsspeechtts.TTSTranslator"
    ) as mock_tts:
        mock_tts.return_value.speak.return_value = b""
        yield mock_tts


async def test_service_say(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts,
    service_calls: list[ServiceCall],
) -> None:
    """Test service call say."""

    await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {"platform": "microsoft", "api_key": ""}}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "microsoft_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.OK
    )

    assert len(mock_tts.mock_calls) == 2

    assert mock_tts.mock_calls[1][2] == {
        "language": "en-us",
        "gender": "Female",
        "voiceType": "JennyNeural",
        "output": "audio-24khz-96kbitrate-mono-mp3",
        "rate": "0%",
        "volume": "0%",
        "pitch": "default",
        "contour": "",
        "text": "There is a person at the front door.",
    }


async def test_service_say_en_gb_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts,
    service_calls: list[ServiceCall],
) -> None:
    """Test service call say with en-gb code in the config."""

    await async_setup_component(
        hass,
        tts.DOMAIN,
        {
            tts.DOMAIN: {
                "platform": "microsoft",
                "api_key": "",
                "language": "en-gb",
                "type": "AbbiNeural",
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "microsoft_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.OK
    )

    assert len(mock_tts.mock_calls) == 2
    assert mock_tts.mock_calls[1][2] == {
        "language": "en-gb",
        "gender": "Female",
        "voiceType": "AbbiNeural",
        "output": "audio-24khz-96kbitrate-mono-mp3",
        "rate": "0%",
        "volume": "0%",
        "pitch": "default",
        "contour": "",
        "text": "There is a person at the front door.",
    }


async def test_service_say_en_gb_service(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts,
    service_calls: list[ServiceCall],
) -> None:
    """Test service call say with en-gb code in the service."""

    await async_setup_component(
        hass,
        tts.DOMAIN,
        {tts.DOMAIN: {"platform": "microsoft", "api_key": ""}},
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "microsoft_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_LANGUAGE: "en-gb",
            tts.ATTR_OPTIONS: {"type": "AbbiNeural"},
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.OK
    )

    assert len(mock_tts.mock_calls) == 2
    assert mock_tts.mock_calls[1][2] == {
        "language": "en-gb",
        "gender": "Female",
        "voiceType": "AbbiNeural",
        "output": "audio-24khz-96kbitrate-mono-mp3",
        "rate": "0%",
        "volume": "0%",
        "pitch": "default",
        "contour": "",
        "text": "There is a person at the front door.",
    }


async def test_service_say_fa_ir_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts,
    service_calls: list[ServiceCall],
) -> None:
    """Test service call say with fa-ir code in the config."""

    await async_setup_component(
        hass,
        tts.DOMAIN,
        {
            tts.DOMAIN: {
                "platform": "microsoft",
                "api_key": "",
                "language": "fa-ir",
                "type": "DilaraNeural",
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "microsoft_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.OK
    )

    assert len(mock_tts.mock_calls) == 2
    assert mock_tts.mock_calls[1][2] == {
        "language": "fa-ir",
        "gender": "Female",
        "voiceType": "DilaraNeural",
        "output": "audio-24khz-96kbitrate-mono-mp3",
        "rate": "0%",
        "volume": "0%",
        "pitch": "default",
        "contour": "",
        "text": "There is a person at the front door.",
    }


async def test_service_say_fa_ir_service(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts,
    service_calls: list[ServiceCall],
) -> None:
    """Test service call say with fa-ir code in the service."""

    config = {
        tts.DOMAIN: {
            "platform": "microsoft",
            "api_key": "",
            "service_name": "microsoft_say",
        }
    }

    await async_setup_component(hass, tts.DOMAIN, config)
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "microsoft_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_LANGUAGE: "fa-ir",
            tts.ATTR_OPTIONS: {"type": "DilaraNeural"},
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.OK
    )

    assert len(mock_tts.mock_calls) == 2
    assert mock_tts.mock_calls[1][2] == {
        "language": "fa-ir",
        "gender": "Female",
        "voiceType": "DilaraNeural",
        "output": "audio-24khz-96kbitrate-mono-mp3",
        "rate": "0%",
        "volume": "0%",
        "pitch": "default",
        "contour": "",
        "text": "There is a person at the front door.",
    }


def test_supported_languages() -> None:
    """Test list of supported languages."""
    for lang in ("en-us", "fa-ir", "en-gb"):
        assert lang in SUPPORTED_LANGUAGES
    assert "en-US" not in SUPPORTED_LANGUAGES
    for lang in (
        "en",
        "en-uk",
        "english",
        "english (united states)",
        "jennyneural",
        "en-us-jennyneural",
    ):
        assert lang not in {s.lower() for s in SUPPORTED_LANGUAGES}
    assert len(SUPPORTED_LANGUAGES) > 100


async def test_invalid_language(hass: HomeAssistant, mock_tts) -> None:
    """Test setup component with invalid language."""
    await async_setup_component(
        hass,
        tts.DOMAIN,
        {tts.DOMAIN: {"platform": "microsoft", "api_key": "", "language": "en"}},
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            tts.DOMAIN,
            "microsoft_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
            },
            blocking=True,
        )

    assert len(mock_tts.mock_calls) == 0


async def test_service_say_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts,
    service_calls: list[ServiceCall],
) -> None:
    """Test service call say with http error."""
    mock_tts.return_value.speak.side_effect = pycsspeechtts.requests.HTTPError
    await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {"platform": "microsoft", "api_key": ""}}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        tts.DOMAIN,
        "microsoft_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.NOT_FOUND
    )

    assert len(mock_tts.mock_calls) == 2
