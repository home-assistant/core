"""Test TTS platform of Azure OpenAI integration."""

from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
from openai import AuthenticationError, RateLimitError, omit
import pytest

from homeassistant.components import tts
from homeassistant.components.azure_openai.const import CONF_TTS_MODEL, DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_PROMPT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_mock_service
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture
async def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock media player calls."""
    return async_mock_service(hass, MP_DOMAIN, SERVICE_PLAY_MEDIA)


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.mark.parametrize(
    "service_data",
    [
        {
            ATTR_ENTITY_ID: "tts.azure_openai_tts_text_to_speech",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {},
        },
        {
            ATTR_ENTITY_ID: "tts.azure_openai_tts_text_to_speech",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
        },
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_tts(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_create_speech: MagicMock,
    entity_registry: er.EntityRegistry,
    calls: list[ServiceCall],
    service_data: dict[str, Any],
) -> None:
    """Test text to speech generation."""
    entity_id = "tts.azure_openai_tts_text_to_speech"

    entity_entry = entity_registry.async_get(entity_id)
    tts_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "tts"
        )
    )
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == tts_entry.subentry_id
    assert entity_entry.has_entity_name
    assert entity_entry.original_name == "Text-to-speech"

    mock_create_speech.return_value = [b"mock aud", b"io data"]

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE, "marin")
    mock_create_speech.assert_called_once_with(
        model="tts-deployment",
        voice=voice_id,
        input="There is a person at the front door.",
        instructions=omit,
        speed=1.0,
        response_format="mp3",
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_sends_configured_instructions(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_create_speech: MagicMock,
    calls: list[ServiceCall],
) -> None:
    """Test a configured prompt is sent as speech instructions."""
    tts_entry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "tts"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        tts_entry,
        data={**tts_entry.data, CONF_PROMPT: "Speak slowly and calmly."},
    )
    await hass.async_block_till_done()

    mock_create_speech.return_value = [b"mock audio"]

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: "tts.azure_openai_tts_text_to_speech",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {},
        },
        blocking=True,
    )

    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert (
        mock_create_speech.call_args.kwargs["instructions"]
        == "Speak slowly and calmly."
    )


@pytest.mark.parametrize(
    ("preferred_format", "expected_response_format"),
    [
        ("ogg", "opus"),
        ("oga", "opus"),
        ("mp3", "mp3"),
    ],
)
@pytest.mark.usefixtures("mock_init_component")
async def test_tts_preferred_format(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_create_speech: MagicMock,
    calls: list[ServiceCall],
    preferred_format: str,
    expected_response_format: str,
) -> None:
    """Test text to speech preferred format handling."""
    mock_create_speech.return_value = [b"mock audio data"]

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: "tts.azure_openai_tts_text_to_speech",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {tts.ATTR_PREFERRED_FORMAT: preferred_format},
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    mock_create_speech.assert_called_once_with(
        model="tts-deployment",
        voice="marin",
        input="There is a person at the front door.",
        instructions=omit,
        speed=1.0,
        response_format=expected_response_format,
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_raw_preferred_format_returns_pcm(
    hass: HomeAssistant,
    mock_create_speech: MagicMock,
) -> None:
    """Test raw preferred format is returned as pcm."""
    tts_entity = hass.data[tts.DOMAIN].get_entity("tts.azure_openai_tts_text_to_speech")
    mock_create_speech.return_value = [b"mock audio data"]

    result = await tts_entity.async_get_tts_audio(
        "There is a person at the front door.",
        "en-US",
        {tts.ATTR_PREFERRED_FORMAT: "raw", tts.ATTR_VOICE: "custom-voice"},
    )

    assert result == ("pcm", b"mock audio data")
    mock_create_speech.assert_called_once_with(
        model="tts-deployment",
        voice="custom-voice",
        input="There is a person at the front door.",
        instructions=omit,
        speed=1.0,
        response_format="pcm",
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_model_voices_and_unsupported_format(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_speech: MagicMock,
) -> None:
    """Test the model voices and unsupported format fallback."""
    tts_entity = hass.data[tts.DOMAIN].get_entity("tts.azure_openai_tts_text_to_speech")
    mock_create_speech.return_value = [b"mock audio data"]

    assert [
        voice.voice_id for voice in tts_entity.async_get_supported_voices("en-US")
    ] == [
        "marin",
        "cedar",
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
        "verse",
    ]
    assert tts_entity.default_options[tts.ATTR_VOICE] == "marin"
    result = await tts_entity.async_get_tts_audio(
        "There is a person at the front door.",
        "en-US",
        {tts.ATTR_PREFERRED_FORMAT: "unsupported", tts.ATTR_VOICE: "alloy"},
    )

    assert result == ("mp3", b"mock audio data")
    assert mock_create_speech.call_args.kwargs["response_format"] == "mp3"

    tts_entry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "tts"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        tts_entry,
        data={**tts_entry.data, CONF_TTS_MODEL: "tts-hd"},
    )
    assert [
        voice.voice_id for voice in tts_entity.async_get_supported_voices("en-US")
    ] == [
        "alloy",
        "ash",
        "coral",
        "echo",
        "fable",
        "onyx",
        "nova",
        "sage",
        "shimmer",
    ]


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_error_translation(
    hass: HomeAssistant,
    mock_create_speech: MagicMock,
) -> None:
    """Test TTS errors include translation metadata."""
    mock_create_speech.side_effect = RateLimitError(
        response=httpx.Response(status_code=429, request=""),
        body=None,
        message=None,
    )
    tts_entity = hass.data[tts.DOMAIN].get_entity("tts.azure_openai_tts_text_to_speech")

    with pytest.raises(HomeAssistantError) as err:
        await tts_entity.async_get_tts_audio(
            "There is a person at the front door.",
            "en-US",
            {tts.ATTR_PREFERRED_FORMAT: "mp3", tts.ATTR_VOICE: "alloy"},
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "tts_error"


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_authentication_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_speech: MagicMock,
) -> None:
    """Test TTS authentication failures start reauthentication."""
    mock_create_speech.side_effect = AuthenticationError(
        response=httpx.Response(status_code=401, request=""),
        body=None,
        message=None,
    )
    tts_entity = hass.data[tts.DOMAIN].get_entity("tts.azure_openai_tts_text_to_speech")

    with (
        patch.object(mock_config_entry, "async_start_reauth") as mock_reauth,
        pytest.raises(HomeAssistantError),
    ):
        await tts_entity.async_get_tts_audio(
            "There is a person at the front door.",
            "en-US",
            {tts.ATTR_PREFERRED_FORMAT: "mp3", tts.ATTR_VOICE: "alloy"},
        )

    mock_reauth.assert_called_once_with(hass)


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_create_speech: MagicMock,
    entity_registry: er.EntityRegistry,
    calls: list[ServiceCall],
) -> None:
    """Test exception handling during text to speech generation."""

    mock_create_speech.side_effect = RateLimitError(
        response=httpx.Response(status_code=429, request=""),
        body=None,
        message=None,
    )

    service_data = {
        ATTR_ENTITY_ID: "tts.azure_openai_tts_text_to_speech",
        tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
        tts.ATTR_MESSAGE: "There is a person at the front door.",
        tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
    }

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )
    mock_create_speech.assert_called_once_with(
        model="tts-deployment",
        voice="voice1",
        input="There is a person at the front door.",
        instructions=omit,
        speed=1.0,
        response_format="mp3",
    )
