"""Tests for the Google Generative AI Conversation TTS entity."""

from __future__ import annotations

from collections.abc import Generator
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from google.genai import types
from google.genai.errors import APIError
import pytest

from homeassistant.components import tts
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    DOMAIN,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_mock_service
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator

API_ERROR_500 = APIError("test", response_json={})
TEST_CHAT_MODEL = "models/some-tts-model"


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
    client.aio.models.generate_content = AsyncMock(
        return_value=types.GenerateContentResponse(
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
    mock_genai_client: AsyncMock,
) -> None:
    """Set up the test environment."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=config, version=2)
    config_entry.add_to_hass(hass)

    sub_entry = ConfigSubentry(
        data={
            tts.CONF_LANG: "en-US",
            CONF_CHAT_MODEL: TEST_CHAT_MODEL,
        },
        subentry_type="tts",
        title="Google AI TTS",
        subentry_id="test_subentry_tts_id",
        unique_id=None,
    )

    config_entry.runtime_data = mock_genai_client

    hass.config_entries.async_add_subentry(config_entry, sub_entry)
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Return config."""
    return {
        CONF_API_KEY: "bla",
    }


@pytest.mark.parametrize(
    "service_data",
    [
        {
            ATTR_ENTITY_ID: "tts.google_ai_tts",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {},
        },
        {
            ATTR_ENTITY_ID: "tts.google_ai_tts",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
        },
    ],
)
@pytest.mark.usefixtures("setup")
async def test_tts_service_speak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    service_data: dict[str, Any],
) -> None:
    """Test tts service."""

    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.aio.models.generate_content.reset_mock()

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
    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE, "zephyr")

    tts_entity._genai_client.aio.models.generate_content.assert_called_once_with(
        model=TEST_CHAT_MODEL,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_id)
                )
            ),
            temperature=RECOMMENDED_TEMPERATURE,
            top_k=RECOMMENDED_TOP_K,
            top_p=RECOMMENDED_TOP_P,
            max_output_tokens=RECOMMENDED_MAX_TOKENS,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
            ],
        ),
    )


@pytest.mark.usefixtures("setup")
async def test_tts_service_speak_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
) -> None:
    """Test service call with HTTP response 500."""
    service_data = {
        ATTR_ENTITY_ID: "tts.google_ai_tts",
        tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
        tts.ATTR_MESSAGE: "There is a person at the front door.",
        tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
    }
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.aio.models.generate_content.reset_mock()
    tts_entity._genai_client.aio.models.generate_content.side_effect = API_ERROR_500

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

    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE)

    tts_entity._genai_client.aio.models.generate_content.assert_called_once_with(
        model=TEST_CHAT_MODEL,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_id)
                )
            ),
            temperature=RECOMMENDED_TEMPERATURE,
            top_k=RECOMMENDED_TOP_K,
            top_p=RECOMMENDED_TOP_P,
            max_output_tokens=RECOMMENDED_MAX_TOKENS,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=RECOMMENDED_HARM_BLOCK_THRESHOLD,
                ),
            ],
        ),
    )
