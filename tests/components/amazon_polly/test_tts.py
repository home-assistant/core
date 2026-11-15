"""Tests for the Amazon Polly text-to-speech platform."""

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from botocore.exceptions import ClientError, EndpointConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import tts
from homeassistant.components.amazon_polly.const import DOMAIN
from homeassistant.components.amazon_polly.helpers import (
    CannotConnect,
    InvalidAuth,
    async_connect,
)
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM, EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import ENTRY_DATA

from tests.components.tts.common import retrieve_media

ENTITY_ID = "tts.amazon_polly_us_east_1_text_to_speech"
CONFIG = {
    CONF_PLATFORM: DOMAIN,
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
}
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
async def setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_polly_client: AsyncMock,
) -> None:
    """Set up the Amazon Polly config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_entry")
async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the text-to-speech entity."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    entity = hass.data[tts.DOMAIN].get_entity(ENTITY_ID)
    assert entity.default_language == "en-US"
    assert entity.async_get_supported_voices("en-GB") == [
        tts.Voice("Amy", "Amy"),
        tts.Voice("Brian", "Brian"),
    ]


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    ("service_data", "expected_call"),
    [
        pytest.param({}, {"VoiceId": "Joanna", "Engine": "standard"}, id="defaults"),
        pytest.param(
            {
                tts.ATTR_LANGUAGE: "en-GB",
                tts.ATTR_OPTIONS: {"voice": "Amy", "engine": "neural"},
            },
            {"VoiceId": "Amy", "Engine": "neural"},
            id="options",
        ),
        pytest.param(
            {tts.ATTR_OPTIONS: {"voice": "Danielle"}},
            {"VoiceId": "Danielle", "Engine": "neural"},
            id="voice_without_default_engine",
        ),
    ],
)
async def test_tts_speak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    mock_polly_client: AsyncMock,
    service_data: dict[str, Any],
    expected_call: dict[str, str],
) -> None:
    """Test the speak action synthesizes with Polly."""
    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            **service_data,
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
    mock_polly_client.synthesize_speech.assert_awaited_once_with(
        OutputFormat="mp3",
        SampleRate="22050",
        Text="There is a person at the front door.",
        TextType="text",
        **expected_call,
    )


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    ("language", "options", "synthesis_error"),
    [
        pytest.param("en-US", {"voice": "Nobody"}, None, id="unknown_voice"),
        pytest.param("en-GB", {}, None, id="language_not_supported"),
        pytest.param(
            "en-GB", {"voice": "Brian", "engine": "neural"}, None, id="engine"
        ),
        pytest.param(
            "en-US",
            {},
            ClientError(
                {"Error": {"Code": "TextLengthExceededException", "Message": "Long"}},
                "SynthesizeSpeech",
            ),
            id="synthesis_failed",
        ),
    ],
)
async def test_tts_errors(
    hass: HomeAssistant,
    mock_polly_client: AsyncMock,
    language: str,
    options: dict[str, str],
    synthesis_error: Exception | None,
) -> None:
    """Test invalid requests and Polly failures raise errors."""
    mock_polly_client.synthesize_speech.side_effect = synthesis_error
    entity = hass.data[tts.DOMAIN].get_entity(ENTITY_ID)

    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("Hello", language, options)


@pytest.mark.parametrize(
    ("config", "issue_id", "entry_states"),
    [
        pytest.param(
            ENTRY_DATA, "deprecated_yaml", [ConfigEntryState.LOADED], id="imported"
        ),
        pytest.param(
            {"profile_name": "polly"},
            "deprecated_yaml_import_issue_credentials",
            [],
            id="profile",
        ),
    ],
)
async def test_legacy_yaml(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    issue_registry: ir.IssueRegistry,
    mock_polly_client: AsyncMock,
    config: dict[str, str],
    issue_id: str,
    entry_states: list[ConfigEntryState],
) -> None:
    """Test the YAML platform keeps working, is imported and raises an issue."""
    assert await async_setup_component(
        hass, tts.DOMAIN, {tts.DOMAIN: {CONF_PLATFORM: DOMAIN} | config}
    )
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    entries = hass.config_entries.async_entries(DOMAIN)
    assert [entry.state for entry in entries] == entry_states

    await hass.services.async_call(
        tts.DOMAIN,
        "amazon_polly_say",
        {
            ATTR_ENTITY_ID: "media_player.something",
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


async def _say(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    service_data: dict[str, Any],
) -> HTTPStatus:
    """Call the say action and fetch the generated media."""
    await hass.services.async_call(
        tts.DOMAIN,
        "amazon_polly_say",
        {
            ATTR_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: MESSAGE,
            **service_data,
        },
        blocking=True,
    )
    assert len(service_calls) == 2
    return await retrieve_media(
        hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
    )


@pytest.mark.parametrize(
    ("config", "service_data", "expected_call"),
    [
        pytest.param(
            {},
            {},
            {
                "VoiceId": "Joanna",
                "Engine": "standard",
                "OutputFormat": "mp3",
                "SampleRate": "22050",
                "TextType": "text",
            },
            id="defaults",
        ),
        pytest.param(
            {
                "voice": "Brian",
                "output_format": "ogg_vorbis",
                "sample_rate": "16000",
                "text_type": "ssml",
            },
            {},
            {
                "VoiceId": "Brian",
                "Engine": "standard",
                "OutputFormat": "ogg_vorbis",
                "SampleRate": "16000",
                "TextType": "ssml",
            },
            id="yaml_options",
        ),
        pytest.param(
            {},
            {
                tts.ATTR_LANGUAGE: "en-GB",
                tts.ATTR_OPTIONS: {"voice": "Amy", "engine": "neural"},
            },
            {
                "VoiceId": "Amy",
                "Engine": "neural",
                "OutputFormat": "mp3",
                "SampleRate": "22050",
                "TextType": "text",
            },
            id="call_options",
        ),
    ],
)
async def test_say(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    mock_polly_client: AsyncMock,
    config: dict[str, str],
    service_data: dict[str, Any],
    expected_call: dict[str, str],
) -> None:
    """Test the say action synthesizes with Polly."""
    assert await async_setup_component(hass, tts.DOMAIN, {tts.DOMAIN: CONFIG | config})
    await hass.async_block_till_done()

    assert await _say(hass, hass_client, service_calls, service_data) == HTTPStatus.OK
    mock_polly_client.synthesize_speech.assert_awaited_once_with(
        Text=MESSAGE, **expected_call
    )


async def test_profile(
    hass: HomeAssistant, mock_session: MagicMock, mock_polly_client: AsyncMock
) -> None:
    """Test an AWS profile is used for the session."""
    config = {CONF_PLATFORM: DOMAIN, "profile_name": "polly"}
    assert await async_setup_component(hass, tts.DOMAIN, {tts.DOMAIN: config})
    await hass.async_block_till_done()

    mock_session.assert_called_once_with(profile="polly")
    assert hass.services.has_service(tts.DOMAIN, "amazon_polly_say")


async def test_client_closed_on_shutdown(
    hass: HomeAssistant, mock_polly_client: AsyncMock
) -> None:
    """Test the Polly client is closed when Home Assistant shuts down."""
    assert await async_setup_component(hass, tts.DOMAIN, {tts.DOMAIN: CONFIG})
    await hass.async_block_till_done()
    # Validating the YAML import closes its own client.
    closed = mock_polly_client.__aexit__.await_count

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    # The legacy provider and the imported entry each close their client.
    assert mock_polly_client.__aexit__.await_count == closed + 2


@pytest.mark.parametrize(
    ("service_data", "synthesis_error"),
    [
        pytest.param({tts.ATTR_OPTIONS: {"voice": "Nobody"}}, None, id="unknown_voice"),
        pytest.param({tts.ATTR_LANGUAGE: "en-GB"}, None, id="language_mismatch"),
        pytest.param(
            {
                tts.ATTR_LANGUAGE: "en-GB",
                tts.ATTR_OPTIONS: {"voice": "Brian", "engine": "neural"},
            },
            None,
            id="engine_mismatch",
        ),
        pytest.param(
            {},
            ClientError(
                {"Error": {"Code": "TextLengthExceededException", "Message": "Long"}},
                "SynthesizeSpeech",
            ),
            id="synthesis_failed",
        ),
    ],
)
async def test_say_errors(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    mock_polly_client: AsyncMock,
    service_data: dict[str, Any],
    synthesis_error: Exception | None,
) -> None:
    """Test invalid requests and Polly failures fail the media request."""
    mock_polly_client.synthesize_speech.side_effect = synthesis_error
    assert await async_setup_component(hass, tts.DOMAIN, {tts.DOMAIN: CONFIG})
    await hass.async_block_till_done()

    assert (
        await _say(hass, hass_client, service_calls, service_data)
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )


@pytest.mark.parametrize(
    ("config", "describe_voices_error"),
    [
        pytest.param(
            {"output_format": "pcm", "sample_rate": "24000"},
            None,
            id="invalid_sample_rate",
        ),
        pytest.param(
            {},
            ClientError(
                {"Error": {"Code": "UnrecognizedClientException", "Message": "Bad"}},
                "DescribeVoices",
            ),
            id="invalid_auth",
        ),
        pytest.param(
            {},
            EndpointConnectionError(endpoint_url="https://polly.amazonaws.com"),
            id="cannot_connect",
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_polly_client: AsyncMock,
    config: dict[str, str],
    describe_voices_error: Exception | None,
) -> None:
    """Test the platform isn't set up when the config or Polly fails."""
    mock_polly_client.describe_voices.side_effect = describe_voices_error
    assert await async_setup_component(hass, tts.DOMAIN, {tts.DOMAIN: CONFIG | config})
    await hass.async_block_till_done()

    assert not hass.services.has_service(tts.DOMAIN, "amazon_polly_say")


@pytest.mark.parametrize(
    ("describe_voices_error", "expected_error"),
    [
        pytest.param(asyncio.CancelledError(), asyncio.CancelledError, id="cancelled"),
        pytest.param(KeyError("Id"), KeyError, id="unexpected"),
        pytest.param(
            ClientError(
                {"Error": {"Code": "UnrecognizedClientException", "Message": "Bad"}},
                "DescribeVoices",
            ),
            InvalidAuth,
            id="invalid_auth",
        ),
        pytest.param(
            EndpointConnectionError(endpoint_url="https://polly.amazonaws.com"),
            CannotConnect,
            id="cannot_connect",
        ),
    ],
)
async def test_connect_closes_client_on_failure(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_polly_client: AsyncMock,
    describe_voices_error: BaseException,
    expected_error: type[BaseException],
) -> None:
    """Test the client is closed when loading the voices fails or is cancelled."""
    mock_polly_client.describe_voices.side_effect = describe_voices_error
    client_context = mock_session.return_value.create_client.return_value

    with pytest.raises(expected_error):
        await async_connect(
            hass,
            region="us-east-1",
            access_key_id=CONFIG["aws_access_key_id"],
            secret_access_key=CONFIG["aws_secret_access_key"],
        )

    client_context.__aexit__.assert_awaited_once()
