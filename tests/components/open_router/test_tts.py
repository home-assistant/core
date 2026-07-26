"""Test the OpenRouter TTS entity."""

from collections.abc import AsyncGenerator
from typing import Self
from unittest.mock import MagicMock

from openai import OpenAIError
import pytest

from homeassistant.components.open_router.const import CONF_TTS_VOICE, DOMAIN
from homeassistant.components.open_router.tts import OpenRouterTTSEntity
from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TTSAudioRequest,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import get_generator_from_data

from tests.common import MockConfigEntry


class _MockAudioStreamResponse:
    """Mock the OpenAI SDK's async streamed binary API response."""

    def __init__(self, chunks: list[bytes]) -> None:
        """Initialize with the byte chunks to yield."""
        self._chunks = chunks

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context manager."""

    async def iter_bytes(self) -> AsyncGenerator[bytes]:
        """Yield the mocked audio chunks."""
        for chunk in self._chunks:
            yield chunk


class _MockAudioStreamError:
    """Mock a streamed response that fails when entering the context manager."""

    async def __aenter__(self) -> Self:
        """Raise as if the API call failed."""
        raise OpenAIError

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context manager."""


def _create_entity(hass: HomeAssistant, client: MagicMock) -> OpenRouterTTSEntity:
    """Create an OpenRouter TTS entity with a mocked client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: "openai/gpt-4o-mini-tts",
                    "supported_voices": ["alloy", "echo"],
                    CONF_TTS_VOICE: "echo",
                },
                subentry_id="tts_subentry",
                subentry_type="tts",
                title="OpenRouter TTS",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    entry.runtime_data = client

    return OpenRouterTTSEntity(entry, entry.subentries["tts_subentry"])


async def test_default_options_use_configured_voice(
    hass: HomeAssistant,
) -> None:
    """Test the configured voice is used when model voices are available."""
    entity = _create_entity(hass, MagicMock())

    assert entity.default_options == {"voice": "echo", "preferred_format": "mp3"}


async def test_stream_tts_audio_streams_response_chunks(
    hass: HomeAssistant,
) -> None:
    """Test the audio response is streamed through without being buffered."""
    client = MagicMock()
    client.audio.speech.with_streaming_response.create = MagicMock(
        return_value=_MockAudioStreamResponse([b"abc", b"def"])
    )
    entity = _create_entity(hass, client)

    request = TTSAudioRequest(
        language="en",
        options={ATTR_VOICE: "echo"},
        message_gen=get_generator_from_data(["Hello world"]),
    )
    response = await entity.async_stream_tts_audio(request)

    assert response.extension == "mp3"
    assert b"".join([chunk async for chunk in response.data_gen]) == b"abcdef"
    client.audio.speech.with_streaming_response.create.assert_called_once_with(
        model="openai/gpt-4o-mini-tts",
        voice="echo",
        input="Hello world",
        response_format="mp3",
        speed=1.0,
        extra_headers={
            "X-Title": "Home Assistant",
            "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
        },
    )


@pytest.mark.parametrize(
    ("preferred_format", "expected_extension", "expected_codec"),
    [
        pytest.param("ogg", "ogg", "opus", id="ogg-maps-to-opus-codec"),
        pytest.param("oga", "oga", "opus", id="oga-maps-to-opus-codec"),
        pytest.param("raw", "pcm", "pcm", id="raw-maps-to-pcm"),
        pytest.param("bogus", "mp3", "mp3", id="unsupported-format-falls-back-to-mp3"),
        pytest.param("wav", "wav", "wav", id="supported-format-is-used-as-is"),
    ],
)
async def test_stream_tts_audio_format_mapping(
    hass: HomeAssistant,
    preferred_format: str,
    expected_extension: str,
    expected_codec: str,
) -> None:
    """Test the preferred format is mapped to the extension and codec OpenRouter expects."""
    client = MagicMock()
    client.audio.speech.with_streaming_response.create = MagicMock(
        return_value=_MockAudioStreamResponse([b"abc"])
    )
    entity = _create_entity(hass, client)

    request = TTSAudioRequest(
        language="en",
        options={ATTR_VOICE: "echo", ATTR_PREFERRED_FORMAT: preferred_format},
        message_gen=get_generator_from_data(["Hello world"]),
    )
    response = await entity.async_stream_tts_audio(request)
    [_ async for _ in response.data_gen]

    assert response.extension == expected_extension
    assert (
        client.audio.speech.with_streaming_response.create.call_args.kwargs[
            "response_format"
        ]
        == expected_codec
    )


async def test_stream_tts_audio_raises_on_api_error(
    hass: HomeAssistant,
) -> None:
    """Test an OpenAI error is surfaced as a HomeAssistantError while streaming."""
    client = MagicMock()
    client.audio.speech.with_streaming_response.create = MagicMock(
        return_value=_MockAudioStreamError()
    )
    entity = _create_entity(hass, client)

    request = TTSAudioRequest(
        language="en",
        options={ATTR_VOICE: "echo"},
        message_gen=get_generator_from_data(["Hello world"]),
    )
    response = await entity.async_stream_tts_audio(request)

    with pytest.raises(HomeAssistantError):
        [_ async for _ in response.data_gen]
