"""Test talking to the Voice app."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
import logging
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.voice_support.client import (
    CONNECT_ERRORS,
    AppInfo,
    AudioRun,
    AudioRunRequest,
    UnsupportedVersionError,
    VoiceSupportClient,
    WakeWordAccepted,
    WakeWordRejected,
    normalize_wake_word,
)
from homeassistant.core import HomeAssistant

from .common import (
    Answer,
    FakeWebsocket,
    accepted,
    rejected,
    speech_ended,
    speech_started,
)
from .conftest import HOST, INFO, INFO_URL, PORT


async def _no_audio() -> AsyncGenerator[bytes]:
    return
    yield


@pytest.mark.parametrize(
    ("wake_word", "expected"),
    [
        pytest.param("Okay Nabu", "okay_nabu", id="phrase"),
        pytest.param("okay-nabu", "okay_nabu", id="dashes"),
        pytest.param("okay_nabu", "okay_nabu", id="id"),
        pytest.param("Hey, Jarvis!", "hey_jarvis", id="punctuation"),
    ],
)
def test_normalize_wake_word(wake_word: str, expected: str) -> None:
    """Test the spellings of a wake word come out the same."""
    assert normalize_wake_word(wake_word) == expected


@pytest.mark.usefixtures("app_info")
async def test_update_info(hass: HomeAssistant) -> None:
    """Test reading what the app says about itself."""
    client = VoiceSupportClient(hass, HOST, PORT)
    assert client.info is None
    assert not client.supports_wake_word("okay nabu")

    info = await client.async_update_info()

    assert info.name == "Voice"
    assert info.version == "1.0.0"
    assert info.wake_words == {"okay_nabu": "okay nabu"}
    assert client.info is info
    assert client.supports_wake_word("Okay Nabu")
    assert not client.supports_wake_word("hey jarvis")


async def test_update_info_wrong_api_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test an app speaking another protocol version cannot be used."""
    aioclient_mock.get(INFO_URL, json={**INFO, "api_version": 2})
    client = VoiceSupportClient(hass, HOST, PORT)
    client.info = AppInfo.from_json(INFO)

    with pytest.raises(UnsupportedVersionError) as err:
        await client.async_update_info()

    assert err.value.info.api_version == 2
    assert str(err.value) == "Voice 1.0.0 speaks protocol version 2, not 1"
    assert client.info is None


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"exc": aiohttp.ClientError}, id="unreachable"),
        pytest.param({"status": 500}, id="error"),
        pytest.param({"text": "not json"}, id="garbage"),
        pytest.param({"json": {"name": "Voice", "api_version": 1}}, id="incomplete"),
        pytest.param({"json": {**INFO, "wake_words": [{}]}}, id="nameless_wake_word"),
        pytest.param({"json": {**INFO, "wake_words": "okay nabu"}}, id="wrong_type"),
    ],
)
async def test_update_info_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, response: dict[str, Any]
) -> None:
    """Test an app that cannot be read, or breaks the contract, is forgotten."""
    aioclient_mock.get(INFO_URL, **response)
    client = VoiceSupportClient(hass, HOST, PORT)
    client.info = AppInfo.from_json(INFO)

    with pytest.raises(CONNECT_ERRORS):
        await client.async_update_info()

    assert client.info is None


async def test_start_run_without_info(hass: HomeAssistant) -> None:
    """Test no run is opened with an app that never answered."""
    client = VoiceSupportClient(hass, HOST, PORT)

    assert await client.async_start_run(AudioRunRequest(), _no_audio()) is None


@pytest.mark.parametrize(
    "request_",
    [
        pytest.param(AudioRunRequest(), id="nothing"),
        pytest.param(
            AudioRunRequest(wake_word_phrase="hey jarvis", wake_word_audio_ms=500),
            id="unknown",
        ),
        pytest.param(
            AudioRunRequest(wake_word_phrase="okay nabu"), id="no_wake_word_audio"
        ),
    ],
)
@pytest.mark.usefixtures("app_info")
async def test_start_run_nothing_to_do(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, request_: AudioRunRequest
) -> None:
    """Test no run is opened when the app could neither verify nor endpoint."""
    client = VoiceSupportClient(hass, HOST, PORT)
    await client.async_update_info()
    aioclient_mock.clear_requests()

    assert await client.async_start_run(request_, _no_audio()) is None
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "request_",
    [
        pytest.param(
            AudioRunRequest(wake_word_phrase="okay nabu", wake_word_audio_ms=500),
            id="verify",
        ),
        pytest.param(AudioRunRequest(silence_seconds=1.0), id="endpoint"),
    ],
)
@pytest.mark.parametrize(
    ("info_response", "still_usable"),
    [
        pytest.param({"json": INFO}, True, id="transient"),
        pytest.param({"exc": aiohttp.ClientError}, False, id="gone"),
    ],
)
@pytest.mark.usefixtures("app_info")
async def test_start_run_unreachable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    request_: AudioRunRequest,
    info_response: dict[str, Any],
    still_usable: bool,
) -> None:
    """Test a run the app cannot be reached for goes on without it, and asks again."""
    client = VoiceSupportClient(hass, HOST, PORT)
    await client.async_update_info()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"http://{HOST}:{PORT}/run", exc=aiohttp.ClientError)
    aioclient_mock.get(INFO_URL, **info_response)

    assert await client.async_start_run(request_, _no_audio()) is None

    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 2
    assert (client.info is not None) == still_usable


BYTES_PER_MS = 32
WAKE = b"w" * BYTES_PER_MS * 10
COMMAND = b"c" * BYTES_PER_MS * 10
TAIL = b"t" * BYTES_PER_MS * 10


async def _audio(*chunks: bytes) -> AsyncGenerator[bytes]:
    for chunk in chunks:
        yield chunk


def _run(
    hass: HomeAssistant,
    websocket: FakeWebsocket,
    audio: AsyncIterable[bytes],
    verifies_wake_word: bool = True,
) -> AudioRun:
    return AudioRun(hass, websocket, audio, verifies_wake_word)  # type: ignore[arg-type]


async def _drain(run: AudioRun) -> bytes:
    return b"".join([chunk async for chunk in run.async_stream()])


async def test_run_feeds_the_app_the_whole_run(hass: HomeAssistant) -> None:
    """Test the app hears everything, the wake word audio included, then the end."""
    websocket = FakeWebsocket([(0, accepted(10))])
    run = _run(hass, websocket, _audio(WAKE, COMMAND))

    assert await run.async_wake_word() == WakeWordAccepted(10)
    assert await _drain(run) == WAKE + COMMAND
    assert bytes(websocket.audio) == WAKE + COMMAND
    assert websocket.audio_ended

    await run.async_close()
    assert websocket.closed


async def test_run_verdict_waits_for_more_audio(hass: HomeAssistant) -> None:
    """Test audio keeps going in until the app answers, and none of it is lost."""
    websocket = FakeWebsocket([(2, accepted(10))])
    run = _run(hass, websocket, _audio(WAKE, TAIL, COMMAND))

    assert await run.async_wake_word() == WakeWordAccepted(10)
    assert await _drain(run) == WAKE + TAIL + COMMAND
    assert bytes(websocket.audio) == WAKE + TAIL + COMMAND


async def test_run_unknown_wake_word_has_no_verdict(hass: HomeAssistant) -> None:
    """Test a wake word the app does not know is not waited for at all."""
    websocket = FakeWebsocket()
    run = _run(hass, websocket, _audio(WAKE, COMMAND), verifies_wake_word=False)

    assert await run.async_wake_word() is None
    assert await _drain(run) == WAKE + COMMAND
    assert bytes(websocket.audio) == WAKE + COMMAND


async def test_run_verdict_after_the_audio_ended(hass: HomeAssistant) -> None:
    """Test an app that answers only once it has heard all there is."""
    websocket = FakeWebsocket()
    run = _run(hass, websocket, _audio(WAKE))

    async def _answer_when_ended() -> None:
        while not websocket.audio_ended:
            await asyncio.sleep(0)
        websocket.go_away()

    hass.async_create_task(_answer_when_ended())
    assert await run.async_wake_word() is None
    assert not run.listening
    assert await _drain(run) == WAKE


async def test_run_verdict_timeout(hass: HomeAssistant) -> None:
    """Test an app that takes too long is not waited for, and the run goes on.

    The source is waiting on the satellite when the timeout fires, as it is
    in practice, and must survive it.
    """
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def _source() -> AsyncGenerator[bytes]:
        while (chunk := await queue.get()) is not None:
            yield chunk

    queue.put_nowait(WAKE)
    websocket = FakeWebsocket()
    run = _run(hass, websocket, _source())

    with patch(
        "homeassistant.components.voice_support.client.WAKE_WORD_VERDICT_SECONDS", 0
    ):
        assert await run.async_wake_word() is None

    assert run.listening
    queue.put_nowait(COMMAND)
    queue.put_nowait(None)
    assert await _drain(run) == WAKE + COMMAND
    assert bytes(websocket.audio) == WAKE + COMMAND


async def test_run_app_goes_away(hass: HomeAssistant) -> None:
    """Test an app that stops answering releases whoever waits on it."""
    websocket = FakeWebsocket()
    run = _run(hass, websocket, _audio(WAKE, COMMAND))
    websocket.go_away()

    assert await run.async_wake_word() is None
    assert not run.listening


async def test_run_app_unreachable(hass: HomeAssistant) -> None:
    """Test audio that cannot be sent stops the run listening, without raising."""
    websocket = FakeWebsocket()
    websocket.unreachable = True
    run = _run(hass, websocket, _audio(WAKE, COMMAND))

    assert await run.async_wake_word() is None
    assert not run.listening
    assert await _drain(run) == WAKE + COMMAND


async def test_run_app_stalls(hass: HomeAssistant) -> None:
    """Test an app that stops taking audio is given up on, and the run goes on."""
    websocket = FakeWebsocket()
    websocket.stalled = True
    run = _run(hass, websocket, _audio(WAKE, COMMAND))

    with patch("homeassistant.components.voice_support.client.SEND_TIMEOUT", 0):
        assert await run.async_wake_word() is None
        assert await _drain(run) == WAKE + COMMAND

    assert not run.listening


async def test_run_source_error_reaches_the_stream(hass: HomeAssistant) -> None:
    """Test what the satellite's stream raises comes out of the run's."""

    async def _source() -> AsyncGenerator[bytes]:
        yield WAKE
        raise OSError("satellite gone")

    websocket = FakeWebsocket()
    run = _run(hass, websocket, _source(), verifies_wake_word=False)

    with pytest.raises(OSError, match="satellite gone"):
        await _drain(run)


async def test_run_close_stops_the_relay(hass: HomeAssistant) -> None:
    """Test closing the run leaves the rest of the satellite's audio alone."""
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def _source() -> AsyncGenerator[bytes]:
        while (chunk := await queue.get()) is not None:
            yield chunk

    queue.put_nowait(WAKE)
    websocket = FakeWebsocket()
    run = _run(hass, websocket, _source(), verifies_wake_word=False)
    await asyncio.sleep(0)

    await run.async_close()
    await hass.async_block_till_done(wait_background_tasks=True)
    queue.put_nowait(COMMAND)
    await asyncio.sleep(0)

    assert websocket.closed
    assert bytes(websocket.audio) == WAKE
    assert queue.qsize() == 1


@pytest.mark.parametrize(
    ("answer", "wake_word", "speech_started_ms", "speech_ended_ms", "logged"),
    [
        pytest.param(accepted(30), WakeWordAccepted(30), None, None, "", id="accepted"),
        pytest.param(
            rejected("last"), WakeWordRejected("last"), None, None, "", id="rejected"
        ),
        pytest.param(
            rejected(), WakeWordRejected(), None, None, "", id="rejected_no_reason"
        ),
        pytest.param(speech_started(20), None, 20, None, "", id="speech_started"),
        pytest.param(speech_ended(40), None, None, 40, "", id="speech_ended"),
        pytest.param(
            {"type": "error", "code": "busy", "message": "Try later"},
            None,
            None,
            None,
            "could not handle the run (busy): Try later",
            id="error",
        ),
        pytest.param(
            {"type": "stt-vad-end"}, None, None, None, "said something odd", id="odd"
        ),
        pytest.param(
            {"type": "wake-word-rejected", "wake_word_output": "last"},
            None,
            None,
            None,
            "said something odd",
            id="wrong_type",
        ),
        pytest.param(
            {"type": "unknown"}, None, None, None, "Ignoring unknown", id="unknown"
        ),
        pytest.param(
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"\x00", None),
            None,
            None,
            None,
            "",
            id="binary",
        ),
    ],
)
async def test_run_answers(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    answer: Answer,
    wake_word: WakeWordAccepted | WakeWordRejected | None,
    speech_started_ms: int | None,
    speech_ended_ms: int | None,
    logged: str,
) -> None:
    """Test what each of the app's messages leaves in the run."""
    caplog.set_level(logging.DEBUG)
    websocket = FakeWebsocket([(0, answer)])
    run = _run(hass, websocket, _audio())
    await asyncio.sleep(0)

    assert run.wake_word == wake_word
    assert run.speech_started_ms == speech_started_ms
    assert run.speech_ended_ms == speech_ended_ms
    assert logged in caplog.text
    assert run.listening
