"""Test talking to the Voice app."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.voice_support.client import (
    AppInfo,
    AudioRun,
    AudioRunRequest,
    InvalidResponseError,
    UnsupportedVersionError,
    VoiceSupportClient,
    WakeWordAccepted,
    WakeWordRejected,
    normalize_wake_word,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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


@pytest.mark.parametrize(
    ("host", "url"),
    [
        pytest.param(HOST, INFO_URL, id="ipv4"),
        pytest.param("2001:db8::1", f"http://[2001:db8::1]:{PORT}/info", id="ipv6"),
    ],
)
async def test_update_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, host: str, url: str
) -> None:
    """Test reading what the app says about itself."""
    aioclient_mock.get(url, json=INFO)
    client = VoiceSupportClient(hass, host, PORT)
    assert client.info is None

    info = await client.async_update_info()

    assert info.name == "Voice"
    assert info.version == "1.0.0"
    assert info.wake_words == {"okay_nabu": "okay nabu"}
    assert client.info is info


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
    ("response", "error"),
    [
        pytest.param(
            {"exc": aiohttp.ClientError}, aiohttp.ClientError, id="unreachable"
        ),
        pytest.param({"status": 500}, aiohttp.ClientResponseError, id="error"),
        pytest.param(
            {"text": "not json", "headers": {"Content-Type": "application/json"}},
            InvalidResponseError,
            id="garbage",
        ),
        pytest.param(
            {"json": {"name": "Voice", "api_version": 1}},
            InvalidResponseError,
            id="incomplete",
        ),
        pytest.param(
            {"json": {**INFO, "wake_words": [{}]}},
            InvalidResponseError,
            id="nameless_wake_word",
        ),
        pytest.param(
            {"json": {**INFO, "wake_words": [{"id": None}]}},
            InvalidResponseError,
            id="wake_word_id_not_text",
        ),
        *[
            pytest.param(
                {"json": {**INFO, field: value}}, InvalidResponseError, id=name
            )
            for field, value, name in (
                ("name", None, "invalid_name"),
                ("version", 1, "invalid_version"),
                ("api_version", "1", "invalid_api_version"),
                ("wake_words", [None], "invalid_wake_word"),
                ("wake_words", [{"id": "okay_nabu", "phrase": 42}], "invalid_phrase"),
            )
        ],
        pytest.param(
            {"json": {**INFO, "wake_words": "okay nabu"}},
            InvalidResponseError,
            id="wrong_type",
        ),
    ],
)
async def test_update_info_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    error: type[Exception],
) -> None:
    """Test an app that cannot be read, or breaks the contract, is forgotten."""
    aioclient_mock.get(INFO_URL, **response)
    client = VoiceSupportClient(hass, HOST, PORT)
    client.info = AppInfo.from_json(INFO)

    with pytest.raises(error):
        await client.async_update_info()

    assert client.info is None


@pytest.mark.parametrize("error", [AttributeError, KeyError, TypeError, ValueError])
async def test_update_info_unexpected_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, error: type[Exception]
) -> None:
    """Test errors outside response parsing are not handled as client failures."""
    aioclient_mock.get(INFO_URL, exc=error)
    client = VoiceSupportClient(hass, HOST, PORT)

    with pytest.raises(error):
        await client.async_update_info()


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
@pytest.mark.usefixtures("app_info")
async def test_start_run_unreachable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    request_: AudioRunRequest,
) -> None:
    """Test a failed connection clears app info and falls back to local processing."""
    client = VoiceSupportClient(hass, HOST, PORT)
    await client.async_update_info()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"http://{HOST}:{PORT}/run", exc=aiohttp.ClientError)

    assert await client.async_start_run(request_, _no_audio()) is None
    assert await client.async_start_run(request_, _no_audio()) is None
    assert client.info is None
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    ("request_", "run_start"),
    [
        pytest.param(
            AudioRunRequest(
                satellite_id="assist_satellite.kitchen",
                wake_word_phrase="okay nabu",
                wake_word_audio_ms=500,
                silence_seconds=1.0,
            ),
            {
                "type": "run-start",
                "satellite_id": "assist_satellite.kitchen",
                "wake_word_phrase": "okay nabu",
                "wake_word_audio_ms": 500,
                "silence_seconds": 1.0,
            },
            id="verify_and_endpoint",
        ),
        pytest.param(
            AudioRunRequest(silence_seconds=1.0),
            {
                "type": "run-start",
                "satellite_id": None,
                "wake_word_phrase": None,
                "wake_word_audio_ms": 0,
                "silence_seconds": 1.0,
            },
            id="endpoint",
        ),
    ],
)
@pytest.mark.usefixtures("app_info")
async def test_start_run(
    hass: HomeAssistant, request_: AudioRunRequest, run_start: dict[str, Any]
) -> None:
    """Test a run is opened with what the app needs to know about it."""
    client = VoiceSupportClient(hass, HOST, PORT)
    await client.async_update_info()
    websocket = FakeWebsocket()
    session = Mock(wraps=async_get_clientsession(hass))
    session.ws_connect = AsyncMock(return_value=websocket)

    with patch(
        "homeassistant.components.voice_support.client.async_get_clientsession",
        return_value=session,
    ):
        run = await client.async_start_run(request_, _audio(WAKE))

    assert run is not None
    assert str(session.ws_connect.call_args.args[0]) == f"http://{HOST}:{PORT}/run"
    assert websocket.run_start == run_start
    assert await _drain(run) == WAKE
    await run.async_close()
    assert websocket.closed


@pytest.mark.usefixtures("app_info")
async def test_start_run_refused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a refused run closes its websocket and clears app info."""
    client = VoiceSupportClient(hass, HOST, PORT)
    await client.async_update_info()
    aioclient_mock.clear_requests()
    aioclient_mock.get(INFO_URL, json=INFO)
    websocket = FakeWebsocket()
    websocket.unreachable = True
    session = Mock(wraps=async_get_clientsession(hass))
    session.ws_connect = AsyncMock(return_value=websocket)

    with patch(
        "homeassistant.components.voice_support.client.async_get_clientsession",
        return_value=session,
    ):
        run = await client.async_start_run(
            AudioRunRequest(silence_seconds=1.0), _no_audio()
        )

    assert run is None
    assert websocket.closed
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 0
    assert client.info is None


@pytest.mark.usefixtures("app_info")
async def test_start_run_cancelled(hass: HomeAssistant) -> None:
    """Test cancellation while starting a run closes the websocket."""
    client = VoiceSupportClient(hass, HOST, PORT)
    await client.async_update_info()
    websocket = FakeWebsocket()
    session = Mock(wraps=async_get_clientsession(hass))
    session.ws_connect = AsyncMock(return_value=websocket)

    with (
        patch(
            "homeassistant.components.voice_support.client.async_get_clientsession",
            return_value=session,
        ),
        patch.object(websocket, "send_json", side_effect=asyncio.CancelledError),
        pytest.raises(asyncio.CancelledError),
    ):
        await client.async_start_run(AudioRunRequest(silence_seconds=1.0), _no_audio())

    assert websocket.closed


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


async def test_run_final_event_timeout(hass: HomeAssistant) -> None:
    """Test a missing final app event does not prevent audio completion."""
    websocket = FakeWebsocket()
    with patch("homeassistant.components.voice_support.client.FINAL_EVENT_TIMEOUT", 0):
        run = _run(hass, websocket, _audio(WAKE), verifies_wake_word=False)
        async with asyncio.timeout(1):
            assert await _drain(run) == WAKE

    assert websocket.audio_ended
    await run.async_close()


async def test_run_close_while_waiting_for_final_event(hass: HomeAssistant) -> None:
    """Test closing a run releases the stream while it waits for app events."""
    websocket = FakeWebsocket()
    run = _run(hass, websocket, _audio(WAKE), verifies_wake_word=False)
    while not websocket.audio_ended:
        await asyncio.sleep(0)

    async with asyncio.timeout(0.1):
        await run.async_close()
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


async def test_run_app_breaks_off(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an app whose answers cannot be read any more is given up on."""
    caplog.set_level(logging.DEBUG)
    websocket = FakeWebsocket([(0, aiohttp.ClientConnectionError("gone"))])
    run = _run(hass, websocket, _audio(WAKE, COMMAND))

    assert await run.async_wake_word() is None
    assert not run.listening
    assert "The app went away mid-run" in caplog.text


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
        async with asyncio.timeout(0.1):
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


async def test_run_error_ends_the_run(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an app that cannot take the run releases whoever waits on it."""
    websocket = FakeWebsocket(
        [(0, {"type": "error", "code": "busy", "message": "Try later"})]
    )
    run = _run(hass, websocket, _audio(WAKE, COMMAND))

    assert await run.async_wake_word() is None
    assert not run.listening
    assert "could not handle the run (busy): Try later" in caplog.text


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
            {"type": "stt-vad-end", "timestamp": "40"},
            None,
            None,
            None,
            "said something odd",
            id="timestamp_not_a_number",
        ),
        pytest.param(
            accepted(-1), None, None, None, "said something odd", id="negative"
        ),
        *[
            pytest.param(answer, None, None, None, "said something odd", id=name)
            for name, answer in (
                ("missing_type", {}),
                ("invalid_type", {"type": []}),
                ("missing_output", {"type": "wake-word-end"}),
                ("missing_boundary", {"type": "wake-word-end", "wake_word_output": {}}),
                (
                    "invalid_reason",
                    {"type": "wake-word-rejected", "wake_word_output": {"reason": 42}},
                ),
                ("invalid_error", {"type": "error", "code": 42, "message": "busy"}),
                ("invalid_json", aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "{", None)),
                (
                    "invalid_event",
                    aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "[]", None),
                ),
            )
        ],
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


@pytest.mark.parametrize(
    "wake_word", [{"id": "okay_nabu"}, {"id": "okay_nabu", "phrase": None}]
)
async def test_update_info_optional_phrase(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    wake_word: dict[str, str | None],
) -> None:
    """Test optional phrases and extra response fields are accepted."""
    aioclient_mock.get(
        INFO_URL, json={**INFO, "wake_words": [wake_word], "extra": True}
    )
    client = VoiceSupportClient(hass, HOST, PORT)

    info = await client.async_update_info()

    assert info.wake_words == {"okay_nabu": None}
