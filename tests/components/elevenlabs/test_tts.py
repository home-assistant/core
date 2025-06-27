"""Tests for the ElevenLabs TTS entity."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from elevenlabs.core import ApiError
from elevenlabs.types import GetVoicesResponse, VoiceSettings
import pytest

from homeassistant.components import tts
from homeassistant.components.elevenlabs.const import (
    ATTR_MODEL,
    CONF_MODEL,
    CONF_SIMILARITY,
    CONF_STABILITY,
    CONF_STYLE,
    CONF_USE_SPEAKER_BOOST,
    CONF_VOICE,
    DEFAULT_SIMILARITY,
    DEFAULT_STABILITY,
    DEFAULT_STYLE,
    DEFAULT_USE_SPEAKER_BOOST,
    DOMAIN,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config

from .const import MOCK_MODELS, MOCK_VOICES

from tests.common import MockConfigEntry, async_mock_service
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


class FakeAudioGenerator:
    """Mock audio generator for ElevenLabs TTS."""

    def __aiter__(self):
        """Mock async iterator for audio parts."""

        async def _gen():
            yield b"audio-part-1"
            yield b"audio-part-2"

        return _gen()


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
def mock_similarity():
    """Mock similarity."""
    return DEFAULT_SIMILARITY / 2


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    config_data: dict[str, Any],
    config_options: dict[str, Any],
    config_options_voice: dict[str, Any],
    request: pytest.FixtureRequest,
    mock_async_client: AsyncMock,
) -> AsyncMock:
    """Set up the test environment."""
    if request.param == "mock_config_entry_setup":
        await mock_config_entry_setup(hass, config_data, config_options)
    elif request.param == "mock_config_entry_setup_voice":
        await mock_config_entry_setup(hass, config_data, config_options_voice)
    else:
        raise RuntimeError("Invalid setup fixture")

    await hass.async_block_till_done()

    return mock_async_client


@pytest.fixture(name="config_data")
def config_data_fixture() -> dict[str, Any]:
    """Return config data."""
    return {}


@pytest.fixture(name="config_options")
def config_options_fixture() -> dict[str, Any]:
    """Return config options."""
    return {}


@pytest.fixture(name="config_options_voice")
def config_options_voice_fixture(mock_similarity) -> dict[str, Any]:
    """Return config options."""
    return {
        CONF_SIMILARITY: mock_similarity,
        CONF_STABILITY: DEFAULT_STABILITY,
        CONF_STYLE: DEFAULT_STYLE,
        CONF_USE_SPEAKER_BOOST: DEFAULT_USE_SPEAKER_BOOST,
    }


async def mock_config_entry_setup(
    hass: HomeAssistant, config_data: dict[str, Any], config_options: dict[str, Any]
) -> None:
    """Mock config entry setup."""
    default_config_data = {
        CONF_API_KEY: "api_key",
    }
    default_config_options = {
        CONF_VOICE: "voice1",
        CONF_MODEL: "model1",
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=default_config_data | config_data,
        options=default_config_options | config_options,
    )
    config_entry.add_to_hass(hass)
    client_mock = AsyncMock()
    client_mock.voices.get_all.return_value = GetVoicesResponse(voices=MOCK_VOICES)
    client_mock.models.list.return_value = MOCK_MODELS
    with patch(
        "homeassistant.components.elevenlabs.AsyncElevenLabs", return_value=client_mock
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.mark.parametrize(
    "config_data",
    [
        {},
        {tts.CONF_LANG: "de"},
        {tts.CONF_LANG: "en"},
        {tts.CONF_LANG: "ja"},
        {tts.CONF_LANG: "es"},
    ],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {ATTR_MODEL: "model2"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
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
    tts_entity._client.text_to_speech.convert = MagicMock(
        return_value=FakeAudioGenerator()
    )

    assert tts_entity._voice_settings == VoiceSettings(
        stability=DEFAULT_STABILITY,
        similarity_boost=DEFAULT_SIMILARITY,
        style=DEFAULT_STYLE,
        use_speaker_boost=DEFAULT_USE_SPEAKER_BOOST,
    )

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
    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE, "voice1")
    model_id = service_data[tts.ATTR_OPTIONS].get(ATTR_MODEL, "model1")

    tts_entity._client.text_to_speech.convert.assert_called_once_with(
        text="There is a person at the front door.",
        voice_id=voice_id,
        model_id=model_id,
        voice_settings=tts_entity._voice_settings,
    )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "de",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_LANGUAGE: "es",
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
    """Test service call say with other langcodes in the config."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._client.text_to_speech.convert = MagicMock(
        return_value=FakeAudioGenerator()
    )

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

    tts_entity._client.text_to_speech.convert.assert_called_once_with(
        text="There is a person at the front door.",
        voice_id="voice1",
        model_id="model1",
        voice_settings=tts_entity._voice_settings,
    )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
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
    """Test service call say with http response 400."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._client.text_to_speech.convert = MagicMock(
        return_value=FakeAudioGenerator()
    )
    tts_entity._client.text_to_speech.convert.side_effect = ApiError

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

    tts_entity._client.text_to_speech.convert.assert_called_once_with(
        text="There is a person at the front door.",
        voice_id="voice1",
        model_id="model1",
        voice_settings=tts_entity._voice_settings,
    )


@pytest.mark.parametrize(
    "config_data",
    [
        {},
        {tts.CONF_LANG: "de"},
        {tts.CONF_LANG: "en"},
        {tts.CONF_LANG: "ja"},
        {tts.CONF_LANG: "es"},
    ],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup_voice",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
            },
        ),
    ],
    indirect=["setup"],
)
async def test_tts_service_speak_voice_settings(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
    mock_similarity: float,
) -> None:
    """Test tts service."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._client.text_to_speech.convert = MagicMock(
        return_value=FakeAudioGenerator()
    )
    assert tts_entity._voice_settings == VoiceSettings(
        stability=DEFAULT_STABILITY,
        similarity_boost=mock_similarity,
        style=DEFAULT_STYLE,
        use_speaker_boost=DEFAULT_USE_SPEAKER_BOOST,
    )

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

    tts_entity._client.text_to_speech.convert.assert_called_once_with(
        text="There is a person at the front door.",
        voice_id="voice2",
        model_id="model1",
        voice_settings=tts_entity._voice_settings,
    )


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.mock_title",
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
    """Test service call say with http response 200."""
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._client.text_to_speech.convert = MagicMock(
        return_value=FakeAudioGenerator()
    )

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

    tts_entity._client.text_to_speech.convert.assert_called_once_with(
        text="There is a person at the front door.",
        voice_id="voice1",
        voice_settings=VoiceSettings(
            stability=0.5, similarity_boost=0.75, style=0.0, use_speaker_boost=True
        ),
        model_id="model1",
    )
