"""Tests for the ElevenLabs TTS entity."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Any, Self
from unittest.mock import AsyncMock, MagicMock

from elevenlabs.core import ApiError
from elevenlabs.types import VoiceSettings
import pytest

from homeassistant.components import tts
from homeassistant.components.elevenlabs.const import (
    ATTR_MODEL,
    CONF_SIMILARITY,
    CONF_STABILITY,
    CONF_STYLE,
    CONF_USE_SPEAKER_BOOST,
    DEFAULT_SIMILARITY,
    DEFAULT_STABILITY,
    DEFAULT_STYLE,
    DEFAULT_USE_SPEAKER_BOOST,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.tts import TTSAudioRequest
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config

from tests.common import async_mock_service
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


class _FakeResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


class _AsyncByteStream:
    """Async iterator that yields bytes and exposes response headers like ElevenLabs' stream."""

    def __init__(self, chunks: list[bytes], request_id: str | None = None) -> None:
        self._chunks = chunks
        self._i = 0

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self

    async def __anext__(self) -> bytes:
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        b = self._chunks[self._i]
        self._i += 1
        await asyncio.sleep(0)  # let loop breathe; mirrors real async iterator
        return b


class _AsyncStreamResponse:
    """Async context manager that mimics ElevenLabs raw stream responses."""

    def __init__(self, chunks: list[bytes], request_id: str | None = None) -> None:
        self.headers = {"request-id": request_id} if request_id else {}
        self.data = _AsyncByteStream(chunks)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.fixture
def capture_stream_calls(monkeypatch: pytest.MonkeyPatch):
    """Patches AsyncElevenLabs.text_to_speech.with_raw_response.stream and captures each call's kwargs.

    Returns:
      calls: list[dict] — kwargs passed into each stream() invocation
      set_next_return(chunks, request_id): sets what the NEXT stream() call yields/returns
    """
    calls: list[dict] = []
    state = {"chunks": [b"X"], "request_id": "rid-1"}  # defaults; override per test

    def set_next_return(
        *, chunks: list[bytes], request_id: str | None, error: Exception | None = None
    ) -> None:
        state["chunks"] = chunks
        state["request_id"] = request_id
        state["error"] = error

    def patch_stream(tts_entity):
        def _mock_stream(**kwargs):
            calls.append(kwargs)
            if state.get("error") is not None:
                raise state["error"]
            return _AsyncStreamResponse(
                chunks=list(state["chunks"]),
                request_id=state["request_id"],
            )

        tts_entity._client.text_to_speech.with_raw_response.stream = _mock_stream

    return calls, set_next_return, patch_stream


@pytest.fixture
def stream_sentence_helpers():
    """Return helpers for queue-driven sentence streaming."""

    def factory(sentence_iter: Iterator[tuple], queue: asyncio.Queue[str | None]):
        async def get_next_part() -> tuple[Any, ...]:
            try:
                return next(sentence_iter)
            except StopIteration:
                await queue.put(None)
                return None, None, None

        async def message_gen() -> AsyncIterator[str]:
            while True:
                part = await queue.get()
                if part is None:
                    break
                yield part

        return get_next_part, message_gen

    return factory


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
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {ATTR_MODEL: "model2"},
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
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
    capture_stream_calls,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test tts service."""
    stream_calls, _, patch_stream = capture_stream_calls
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    patch_stream(tts_entity)

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

    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    assert len(stream_calls) == 1
    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE, "voice1")
    model_id = service_data[tts.ATTR_OPTIONS].get(ATTR_MODEL, "model1")
    language = service_data.get(tts.ATTR_LANGUAGE, tts_entity.default_language)

    call_kwargs = stream_calls[0]
    assert call_kwargs["text"] == "There is a person at the front door."
    assert call_kwargs["voice_id"] == voice_id
    assert call_kwargs["model_id"] == model_id
    assert call_kwargs["voice_settings"] == tts_entity._voice_settings
    assert call_kwargs["output_format"] == "mp3_44100_128"
    assert call_kwargs["language_code"] == language


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
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
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
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
    capture_stream_calls,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with other langcodes in the config."""
    stream_calls, _, patch_stream = capture_stream_calls
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    patch_stream(tts_entity)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(stream_calls) == 1
    language = service_data.get(tts.ATTR_LANGUAGE, tts_entity.default_language)
    call_kwargs = stream_calls[0]
    assert call_kwargs["text"] == "There is a person at the front door."
    assert call_kwargs["voice_id"] == "voice1"
    assert call_kwargs["model_id"] == "model1"
    assert call_kwargs["voice_settings"] == tts_entity._voice_settings
    assert call_kwargs["output_format"] == "mp3_44100_128"
    assert call_kwargs["language_code"] == language


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
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
    capture_stream_calls,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with http response 400."""
    stream_calls, set_next_return, patch_stream = capture_stream_calls
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    patch_stream(tts_entity)
    set_next_return(chunks=[], request_id=None, error=ApiError())

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )

    assert len(stream_calls) == 1
    language = service_data.get(tts.ATTR_LANGUAGE, tts_entity.default_language)
    call_kwargs = stream_calls[0]
    assert call_kwargs["text"] == "There is a person at the front door."
    assert call_kwargs["voice_id"] == "voice1"
    assert call_kwargs["model_id"] == "model1"
    assert call_kwargs["voice_settings"] == tts_entity._voice_settings
    assert call_kwargs["output_format"] == "mp3_44100_128"
    assert call_kwargs["language_code"] == language


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
    ("config_options", "tts_service", "service_data"),
    [
        (
            {
                CONF_SIMILARITY: DEFAULT_SIMILARITY / 2,
                CONF_STABILITY: DEFAULT_STABILITY,
                CONF_STYLE: DEFAULT_STYLE,
                CONF_USE_SPEAKER_BOOST: DEFAULT_USE_SPEAKER_BOOST,
            },
            "speak",
            {
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is a person at the front door.",
                tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
            },
        ),
    ],
)
async def test_tts_service_speak_voice_settings(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    capture_stream_calls,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
    mock_similarity: float,
) -> None:
    """Test tts service."""
    stream_calls, _, patch_stream = capture_stream_calls
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    patch_stream(tts_entity)

    assert tts_entity._voice_settings == VoiceSettings(
        stability=DEFAULT_STABILITY,
        similarity_boost=DEFAULT_SIMILARITY / 2,
        style=DEFAULT_STYLE,
        use_speaker_boost=DEFAULT_USE_SPEAKER_BOOST,
    )

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(stream_calls) == 1
    language = service_data.get(tts.ATTR_LANGUAGE, tts_entity.default_language)
    call_kwargs = stream_calls[0]
    assert call_kwargs["text"] == "There is a person at the front door."
    assert call_kwargs["voice_id"] == "voice2"
    assert call_kwargs["model_id"] == "model1"
    assert call_kwargs["voice_settings"] == tts_entity._voice_settings
    assert call_kwargs["output_format"] == "mp3_44100_128"
    assert call_kwargs["language_code"] == language


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.elevenlabs_text_to_speech",
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
    capture_stream_calls,
    calls: list[ServiceCall],
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service call say with http response 200."""
    stream_calls, _, patch_stream = capture_stream_calls
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    patch_stream(tts_entity)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )

    assert len(stream_calls) == 1
    language = service_data.get(tts.ATTR_LANGUAGE, tts_entity.default_language)
    call_kwargs = stream_calls[0]
    assert call_kwargs["text"] == "There is a person at the front door."
    assert call_kwargs["voice_id"] == "voice1"
    assert call_kwargs["model_id"] == "model1"
    assert call_kwargs["voice_settings"] == VoiceSettings(
        stability=0.5,
        similarity_boost=0.75,
        style=0.0,
        use_speaker_boost=True,
    )
    assert call_kwargs["output_format"] == "mp3_44100_128"
    assert call_kwargs["language_code"] == language


@pytest.mark.parametrize(
    ("setup", "model_id"),
    [
        ("mock_config_entry_setup", "eleven_multilingual_v2"),
    ],
    indirect=["setup"],
)
@pytest.mark.parametrize(
    ("message", "chunks", "request_ids"),
    [
        (
            [
                ["One. ", "Two! ", "Three"],
                ["! ", "Four"],
                ["? ", "Five"],
                ["! ", "Six!"],
            ],
            [b"\x05\x06", b"\x07\x08", b"\x09\x0a", b"\x0b\x0c"],
            ["rid-1", "rid-2", "rid-3", "rid-4"],
        ),
    ],
)
async def test_stream_tts_with_request_ids(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    capture_stream_calls,
    stream_sentence_helpers,
    model_id: str,
    message: list[list[str]],
    chunks: list[bytes],
    request_ids: list[str],
) -> None:
    """Test streaming TTS with request-id stitching."""
    calls, set_next_return, patch_stream = capture_stream_calls

    # Access the TTS entity as in your existing tests; adjust if you use a fixture instead
    tts_entity = hass.data[tts.DOMAIN].get_entity("tts.elevenlabs_text_to_speech")
    patch_stream(tts_entity)

    # Use a queue to control when each part is yielded
    queue = asyncio.Queue()
    prev_request_ids: deque[str] = deque(maxlen=3)  # keep last 3 request IDs
    sentence_iter = iter(zip(message, chunks, request_ids, strict=False))
    get_next_part, message_gen = stream_sentence_helpers(sentence_iter, queue)
    options = {tts.ATTR_VOICE: "voice1", "model": model_id}
    req = TTSAudioRequest(message_gen=message_gen(), language="en", options=options)

    resp = await tts_entity.async_stream_tts_audio(req)
    assert resp.extension == "mp3"

    item, chunk, request_id = await get_next_part()
    if item is not None:
        for part in item:
            await queue.put(part)
    else:
        await queue.put(None)

    set_next_return(chunks=[chunk], request_id=request_id)
    next_item, next_chunk, next_request_id = await get_next_part()
    # Consume bytes; after first chunk, switch next return to emulate second call
    async for b in resp.data_gen:
        assert b == chunk  # each sentence yields its first chunk immediately
        assert "previous_text" not in calls[-1]  # no previous_text for first sentence
        assert "next_text" not in calls[-1]  # no next_text for first
        assert calls[-1].get("previous_request_ids", []) == (
            [] if len(calls) == 1 else list(prev_request_ids)
        )
        prev_request_ids.append(request_id or "")
        item, chunk, request_id = next_item, next_chunk, next_request_id
        if item is not None:
            for part in item:
                await queue.put(part)
            set_next_return(chunks=[chunk], request_id=request_id)
            next_item, next_chunk, next_request_id = await get_next_part()
            if item is None:
                await queue.put(None)
        else:
            await queue.put(None)

    # We expect two stream() invocations (one per sentence batch)
    assert len(calls) == len(message)


@pytest.mark.parametrize(
    ("message", "chunks", "request_ids"),
    [
        (
            [
                ["This is the first sentence. ", "This is "],
                ["the second sentence. "],
            ],
            [b"\x05\x06", b"\x07\x08"],
            ["rid-1", "rid-2"],
        ),
    ],
)
async def test_stream_tts_without_request_ids_eleven_v3(
    setup: AsyncMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    capture_stream_calls,
    stream_sentence_helpers,
    monkeypatch: pytest.MonkeyPatch,
    message: list[list[str]],
    chunks: list[bytes],
    request_ids: list[str],
) -> None:
    """Test streaming TTS without request-id stitching (eleven_v3)."""
    calls, set_next_return, patch_stream = capture_stream_calls
    tts_entity = hass.data[tts.DOMAIN].get_entity("tts.elevenlabs_text_to_speech")
    patch_stream(tts_entity)
    monkeypatch.setattr(
        "homeassistant.components.elevenlabs.tts.MODELS_REQUEST_ID_NOT_SUPPORTED",
        ("model1",),
        raising=False,
    )

    queue = asyncio.Queue()
    sentence_iter = iter(zip(message, chunks, request_ids, strict=False))
    get_next_part, message_gen = stream_sentence_helpers(sentence_iter, queue)
    options = {tts.ATTR_VOICE: "voice1", "model": "model1"}
    req = TTSAudioRequest(message_gen=message_gen(), language="en", options=options)

    resp = await tts_entity.async_stream_tts_audio(req)
    assert resp.extension == "mp3"

    item, chunk, request_id = await get_next_part()
    if item is not None:
        for part in item:
            await queue.put(part)
    else:
        await queue.put(None)

    set_next_return(chunks=[chunk], request_id=request_id)
    next_item, next_chunk, next_request_id = await get_next_part()
    previous_sentence = None
    # Consume bytes; after first chunk, switch next return to emulate second call
    async for b in resp.data_gen:
        assert b == chunk  # each sentence yields its first chunk immediately
        assert "previous_request_ids" not in calls[-1]  # no previous_request_ids
        assert calls[-1].get("previous_text") == previous_sentence
        previous_sentence = calls[-1]["text"]

        item, chunk, request_id = next_item, next_chunk, next_request_id
        if item is not None:
            for part in item:
                await queue.put(part)
            set_next_return(chunks=[chunk], request_id=request_id)
            next_item, next_chunk, next_request_id = await get_next_part()
            if item is None:
                await queue.put(None)
        else:
            await queue.put(None)

    # We expect two stream() invocations (one per sentence batch)
    assert len(calls) == len(message)
