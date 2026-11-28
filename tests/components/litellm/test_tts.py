"""Test TTS platform of LiteLLM integration."""

from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx2
from openai import APIConnectionError, AuthenticationError, OpenAIError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_mock_service
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import tts
from homeassistant.components.litellm.const import CONF_TTS_VOICE, DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.tts import TextToSpeechCommonOption
from homeassistant.config_entries import SOURCE_REAUTH, ConfigSubentryData
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    CONF_MODEL,
    CONF_URL,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config

from . import setup_integration
from .conftest import TEST_URL

from tests.components.tts.common import retrieve_media

ENTITY_ID = "tts.tts_1"
MESSAGE = "There is a person at the front door."


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
async def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock media player calls."""
    return async_mock_service(hass, MP_DOMAIN, SERVICE_PLAY_MEDIA)


@pytest.fixture
async def tts_config_entry(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> MockConfigEntry:
    """Set up a LiteLLM entry with a TTS subentry."""
    entry = MockConfigEntry(
        title="localhost:4000",
        domain=DOMAIN,
        data={CONF_URL: TEST_URL, CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_MODEL: "tts-1", CONF_TTS_VOICE: "alloy"},
                subentry_id="TTS",
                subentry_type="tts",
                title="tts-1",
                unique_id=None,
            )
        ],
    )
    await setup_integration(hass, entry)
    return entry


async def _speak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    options: dict[str, Any],
) -> HTTPStatus:
    """Speak a message and return the status of fetching its audio."""
    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: MESSAGE,
            tts.ATTR_OPTIONS: options,
        },
        blocking=True,
    )
    return await retrieve_media(
        hass, hass_client, calls[-1].data[ATTR_MEDIA_CONTENT_ID]
    )


@pytest.mark.usefixtures("tts_config_entry")
@pytest.mark.parametrize(
    ("options", "voice"),
    [
        pytest.param({}, "alloy", id="configured-voice"),
        pytest.param(
            {TextToSpeechCommonOption.VOICE: "af_bella"}, "af_bella", id="voice-option"
        ),
    ],
)
async def test_tts(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_openai_client: AsyncMock,
    calls: list[ServiceCall],
    options: dict[str, Any],
    voice: str,
) -> None:
    """Test speech is generated with the configured model and voice."""
    mock_openai_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=b"mock audio")
    )

    assert await _speak(hass, hass_client, calls, options) == HTTPStatus.OK
    mock_openai_client.audio.speech.create.assert_awaited_once_with(
        model="tts-1", voice=voice, input=MESSAGE, response_format="mp3"
    )


async def test_tts_new_model_skips_cache(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_openai_client: AsyncMock,
    calls: list[ServiceCall],
    tts_config_entry: MockConfigEntry,
) -> None:
    """Test a message is spoken again by the new model after a model change."""
    mock_openai_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=b"mock audio")
    )
    assert await _speak(hass, hass_client, calls, {}) == HTTPStatus.OK

    subentry = tts_config_entry.subentries["TTS"]
    hass.config_entries.async_update_subentry(
        tts_config_entry,
        subentry,
        data={**subentry.data, CONF_MODEL: "gpt-4o-mini-tts"},
    )
    await hass.async_block_till_done()

    assert await _speak(hass, hass_client, calls, {}) == HTTPStatus.OK
    assert mock_openai_client.audio.speech.create.await_count == 2
    mock_openai_client.audio.speech.create.assert_awaited_with(
        model="gpt-4o-mini-tts", voice="alloy", input=MESSAGE, response_format="mp3"
    )


@pytest.mark.usefixtures("tts_config_entry")
@pytest.mark.parametrize(
    ("side_effect", "available"),
    [
        pytest.param(
            APIConnectionError(request=httpx2.Request("POST", TEST_URL)),
            False,
            id="connection",
        ),
        pytest.param(OpenAIError("unknown voice"), True, id="provider"),
    ],
)
async def test_tts_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_openai_client: AsyncMock,
    calls: list[ServiceCall],
    side_effect: Exception,
    available: bool,
) -> None:
    """Test only connection errors mark the TTS entity unavailable."""
    mock_openai_client.audio.speech.create = AsyncMock(side_effect=side_effect)

    assert (
        await _speak(hass, hass_client, calls, {}) == HTTPStatus.INTERNAL_SERVER_ERROR
    )
    assert (hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE) is available


async def test_tts_auth_error_starts_reauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_openai_client: AsyncMock,
    tts_config_entry: MockConfigEntry,
    calls: list[ServiceCall],
) -> None:
    """Test a rejected API key starts reauthentication."""
    auth_error = AuthenticationError(
        message="invalid api key",
        response=httpx2.Response(401, request=httpx2.Request("POST", TEST_URL)),
        body=None,
    )
    mock_openai_client.audio.speech.create = AsyncMock(side_effect=auth_error)
    mock_openai_client.with_options.return_value.models.list.side_effect = auth_error

    assert (
        await _speak(hass, hass_client, calls, {}) == HTTPStatus.INTERNAL_SERVER_ERROR
    )
    await hass.async_block_till_done()

    assert [
        flow["context"]["source"]
        for flow in tts_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    ] == [SOURCE_REAUTH]
