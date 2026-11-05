"""Test the exchange with the Voice app."""

import asyncio
from collections.abc import Callable

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.voice_support import (
    AudioRun,
    AudioRunRequest,
    WakeWordAccepted,
    WakeWordRejected,
)
from homeassistant.core import HomeAssistant

from .conftest import FakeApp

pytestmark = pytest.mark.usefixtures("socket_enabled")

CHUNK = b"\x01\x02" * 1600  # 100 ms

REQUEST = AudioRunRequest(
    satellite_id="assist_satellite.kitchen",
    wake_word_phrase="okay nabu",
    wake_word_audio_ms=1000,
    silence_seconds=0.7,
)


async def _until(check: Callable[[], bool], timeout: float = 1.0) -> None:
    """Wait for the app's reader task to have caught up."""
    async with asyncio.timeout(timeout):
        while not check():
            await asyncio.sleep(0)


async def _start(
    entry: MockConfigEntry, request: AudioRunRequest = REQUEST
) -> AudioRun:
    run = await entry.runtime_data.async_start_run(request)
    assert run is not None
    return run


async def test_the_app_is_told_what_the_run_is(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test what the app is told when a run opens."""
    run = await _start(setup_integration)
    await _until(lambda: bool(fake_app.requests))
    await run.async_close()

    assert fake_app.requests[0] == {
        "type": "run-start",
        "satellite_id": "assist_satellite.kitchen",
        "wake_word_phrase": "okay nabu",
        "wake_word_audio_ms": 1000,
        "silence_seconds": 0.7,
    }


async def test_the_audio_goes_through(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test the run's audio arrives, and the app is told when it stops."""
    run = await _start(setup_integration)
    await run.async_write(CHUNK)
    await run.async_write(CHUNK)
    await run.async_end_audio()
    await _until(lambda: fake_app.audio_ended)
    await run.async_close()

    assert fake_app.audio == [CHUNK + CHUNK]


async def test_an_accepted_wake_word_carries_the_split(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test where the app put the end of the wake word comes back."""
    fake_app.events = [
        (
            0,
            {
                "type": "wake-word-end",
                "wake_word_output": {
                    "wake_word_phrase": "okay nabu",
                    "wake_word_audio_ms": 940,
                },
            },
        )
    ]
    run = await _start(setup_integration)
    verdict = await run.async_wake_word(1.0)
    await run.async_close()

    assert verdict == WakeWordAccepted(wake_word_audio_ms=940)


async def test_a_refusal_keeps_its_reason(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test a refusal comes back whole."""
    fake_app.events = [
        (
            0,
            {
                "type": "wake-word-rejected",
                "wake_word_output": {
                    "wake_word_phrase": "okay nabu",
                    "reason": "confusable",
                },
            },
        )
    ]
    run = await _start(setup_integration)
    verdict = await run.async_wake_word(1.0)
    await run.async_close()

    assert verdict == WakeWordRejected(reason="confusable")


async def test_a_verdict_can_wait_for_more_audio(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test an app that answers only once it has heard enough."""
    fake_app.events = [
        (
            2,
            {
                "type": "wake-word-end",
                "wake_word_output": {"wake_word_audio_ms": 1000},
            },
        )
    ]
    run = await _start(setup_integration)

    waiting = asyncio.create_task(run.async_wake_word(1.0))
    await run.async_write(CHUNK)
    await run.async_write(CHUNK)
    verdict = await waiting
    await run.async_close()

    assert verdict == WakeWordAccepted(wake_word_audio_ms=1000)


async def test_the_speech_boundaries_come_back(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test where the command begins and ends is read off the run."""
    fake_app.events = [
        (1, {"type": "stt-vad-start", "timestamp": 1840}),
        (2, {"type": "stt-vad-end", "timestamp": 4120}),
    ]
    run = await _start(setup_integration)

    await run.async_write(CHUNK)
    await _until(lambda: run.speech_started_ms is not None)
    assert run.speech_ended_ms is None

    await run.async_write(CHUNK)
    await _until(lambda: run.speech_ended_ms is not None)
    await run.async_close()

    assert run.speech_started_ms == 1840
    assert run.speech_ended_ms == 4120


async def test_an_app_that_is_gone_takes_no_runs(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test the pipeline is left to get on alone."""
    await fake_app.stop()

    assert await setup_integration.runtime_data.async_start_run(REQUEST) is None


async def test_an_app_that_hangs_up_stops_being_listened_to(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test a run whose app went away says so, rather than waiting forever."""
    run = await _start(setup_integration)
    await run.async_write(CHUNK)
    await run.async_end_audio()

    await _until(lambda: not run.listening)
    assert await run.async_wake_word(1.0) is not None  # it answered before going
    await run.async_close()


async def test_no_verdict_within_the_deadline(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test a silent app is given up on rather than waited out."""
    fake_app.events = []
    run = await _start(setup_integration)

    assert await run.async_wake_word(0.01) is None
    await run.async_close()


async def test_something_else_from_the_app_is_ignored(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test an app saying things this does not know leaves the run alone."""
    fake_app.events = [
        (0, {"type": "speaker", "id": "mike"}),
        (0, {"type": "error", "code": "internal", "message": "nope"}),
        (1, {"type": "stt-vad-start", "timestamp": 10}),
    ]
    run = await _start(setup_integration)
    await run.async_write(CHUNK)
    await _until(lambda: run.speech_started_ms is not None)
    await run.async_close()

    assert run.speech_started_ms == 10
    assert run.wake_word is None
