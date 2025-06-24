"""Tests for the Google Generative AI Conversation TTS entity."""

from __future__ import annotations

from collections.abc import Generator
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from google.genai import types
import pytest

from homeassistant.components import tts
from homeassistant.components.google_generative_ai_conversation.tts import (
    ATTR_MODEL,
    DOMAIN,
    RECOMMENDED_TTS_MODEL,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY, CONF_PLATFORM
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from . import API_ERROR_500

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
    return async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
def mock_genai_client() -> Generator[AsyncMock]:
    """Mock genai_client."""
    client = Mock()
    client.aio.models.get = AsyncMock()
    client.models.generate_content.return_value = types.GenerateContentResponse(
        candidates=(
            types.Candidate(
                content=types.Content(
                    parts=(
                        types.Part(
                            inline_data=types.Blob(
                                data=b"raw-audio-bytes",
                                mime_type="audio/L16;rate=24000",
                            )
                        ),
                    )
                )
            ),
        )
    )
    with patch(
        "homeassistant.components.google_generative_ai_conversation.Client",
        return_value=client,
    ) as mock_client:
        yield mock_client


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    config: dict[str, Any],
    request: pytest.FixtureRequest,
    mock_genai_client: AsyncMock,
) -> None:
    """Set up the test environment."""
    if request.param == "mock_setup":
        await mock_setup(hass, config)
    if request.param == "mock_config_entry_setup":
        await mock_config_entry_setup(hass, config)
    else:
        raise RuntimeError("Invalid setup fixture")

    await hass.async_block_till_done()


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Return config."""
    return {
        CONF_API_KEY: "bla",
    }


async def mock_setup(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Mock setup."""
    assert await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {CONF_PLATFORM: DOMAIN} | config}
    )


async def mock_config_entry_setup(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Mock config entry setup."""
    default_config = {tts.CONF_LANG: "en-US"}
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=default_config | config, version=2
    )

    client_mock = Mock()
    client_mock.models.get = None
    client_mock.models.generate_content.return_value = types.GenerateContentResponse(
        candidates=(
            types.Candidate(
                content=types.Content(
                    parts=(
                        types.Part(
                            inline_data=types.Blob(
                                data=b"raw-audio-bytes",
                                mime_type="audio/L16;rate=24000",
                            )
                        ),
                    )
                )
            ),
        )
    )
    config_entry.runtime_data = client_mock
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {ATTR_MODEL: "model2"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2", ATTR_MODEL: "model2"},
            },
        ),
    ],
    indirect=["setup"],
)
async def test_tts_service_speak(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test tts service."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.models.generate_content.reset_mock()

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE, "zephyr")
    model_id = service_data[tts.ATTR_OPTIONS].get(ATTR_MODEL, RECOMMENDED_TTS_MODEL)

    tts_entity._genai_client.models.generate_content.assert_called_once_with(
        model=model_id,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_id)
                )
            ),
        ),
    )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "de-DE",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "it-IT",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
            },
        ),
    ],
    indirect=["setup"],
)
async def test_tts_service_speak_lang_config(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call with languages in the config."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.models.generate_content.reset_mock()

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    tts_entity._genai_client.models.generate_content.assert_called_once_with(
        model=RECOMMENDED_TTS_MODEL,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="voice1")
                )
            ),
        ),
    )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
            },
        ),
    ],
    indirect=["setup"],
)
async def test_tts_service_speak_error(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call with HTTP response 500."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.models.generate_content.reset_mock()
    tts_entity._genai_client.models.generate_content.side_effect = API_ERROR_500

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )

    tts_entity._genai_client.models.generate_content.assert_called_once_with(
        model=RECOMMENDED_TTS_MODEL,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="voice1")
                )
            ),
        ),
    )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_generative_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {},
            },
        ),
    ],
    indirect=["setup"],
)
async def test_tts_service_speak_without_options(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call with HTTP response 200."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.models.generate_content.reset_mock()

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    tts_entity._genai_client.models.generate_content.assert_called_once_with(
        model=RECOMMENDED_TTS_MODEL,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="zephyr")
                )
            ),
        ),
    )
