"""Tests for the Amazon Polly text-to-speech platform."""

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from botocore.exceptions import ClientError, EndpointConnectionError
import pytest
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import tts
from homeassistant.components.amazon_polly.const import DOMAIN
from homeassistant.components.amazon_polly.helpers import (
    CannotConnect,
    InvalidAuth,
    async_connect,
)
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM, EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from tests.components.tts.common import retrieve_media

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
    mock_polly_client.__aexit__.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    mock_polly_client.__aexit__.assert_awaited_once()


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
