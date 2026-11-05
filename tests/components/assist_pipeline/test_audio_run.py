"""Test the pipeline handing a satellite's audio to the Voice app."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
from unittest.mock import patch

import pytest

from homeassistant.components import assist_pipeline, stt
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.components.assist_pipeline.const import MS_PER_CHUNK
from homeassistant.components.voice_support import (
    AudioRunRequest,
    SpeechEnded,
    SpeechStarted,
    WakeWordAccepted,
    WakeWordRejected,
)
from homeassistant.core import Context, HomeAssistant

from .conftest import MockSTTProviderEntity, make_10ms_chunk

WAKE = make_10ms_chunk(b"wake")
WORD = make_10ms_chunk(b"word")
COMMAND = make_10ms_chunk(b"command")
TAIL = make_10ms_chunk(b"tail")

PHRASE = "okay nabu"


class MockRun:
    """A run that says what the test wrote down, when the test said so."""

    def __init__(self, events: list[tuple[int, object]]) -> None:
        """Set up a run that will say ``events`` after that many writes."""
        self.wake_word: WakeWordAccepted | WakeWordRejected | None = None
        self.speech_started_ms: int | None = None
        self.speech_ended_ms: int | None = None
        self.listening = True

        self.audio = bytearray()
        self.writes = 0
        self.audio_ended = False
        self.closed = False
        self._events = list(events)
        self._known = asyncio.Event()
        self._say_what_is_due()

    def _say_what_is_due(self) -> None:
        while self._events and (self._events[0][0] <= self.writes):
            event = self._events.pop(0)[1]
            if isinstance(event, (WakeWordAccepted, WakeWordRejected)):
                self.wake_word = event
                self._known.set()
            elif isinstance(event, SpeechStarted):
                self.speech_started_ms = event.timestamp_ms
            elif isinstance(event, SpeechEnded):
                self.speech_ended_ms = event.timestamp_ms

    def stop_listening(self) -> None:
        """The app went away."""
        self.listening = False
        self._known.set()

    async def async_wake_word(
        self, timeout: float
    ) -> WakeWordAccepted | WakeWordRejected | None:
        """Wait for the verdict, or give up on there being one."""
        try:
            async with asyncio.timeout(timeout):
                await self._known.wait()
        except TimeoutError:
            return None
        return self.wake_word

    async def async_write(self, audio: bytes) -> None:
        """Take the next of the run's audio."""
        self.audio.extend(audio)
        self.writes += 1
        self._say_what_is_due()

    async def async_end_audio(self) -> None:
        """The satellite stopped streaming."""
        self.audio_ended = True

    async def async_close(self) -> None:
        """Let the run go."""
        self.closed = True


class MockClient:
    """The app, as far as the pipeline can tell."""

    def __init__(
        self,
        events: list[tuple[int, object]] | None = None,
        *,
        phrases: set[str] | None = None,
        run: MockRun | None = None,
    ) -> None:
        """Set up an app with a canned run."""
        self.events = events or []
        self.phrases = {PHRASE} if phrases is None else phrases
        self.requests: list[AudioRunRequest] = []
        self.run = run

    def supports_wake_word(self, wake_word_phrase: str) -> bool:
        """Whether the app knows this wake word."""
        return wake_word_phrase in self.phrases

    async def async_start_run(self, request: AudioRunRequest) -> MockRun:
        """Open the run."""
        self.requests.append(request)
        if self.run is None:
            self.run = MockRun(self.events)
        return self.run


async def _audio_stream(*chunks: bytes) -> AsyncGenerator[bytes]:
    for chunk in chunks:
        yield chunk


async def _async_run_pipeline(
    hass: HomeAssistant,
    audio_stream: AsyncIterable[bytes],
    wake_word_audio_ms: int = MS_PER_CHUNK,
    wake_word_phrase: str | None = PHRASE,
    is_vad_enabled: bool = False,
    client: MockClient | None = None,
) -> list[PipelineEvent]:
    """Run a pipeline with ``client`` standing in for an installed app."""
    events: list[PipelineEvent] = []
    with patch(
        "homeassistant.components.voice_support.async_get_client", return_value=client
    ):
        await assist_pipeline.async_pipeline_from_audio_stream(
            hass,
            context=Context(),
            event_callback=events.append,
            stt_metadata=stt.SpeechMetadata(
                language="",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_stream,
            wake_word_phrase=wake_word_phrase,
            wake_word_audio_ms=wake_word_audio_ms,
            audio_settings=assist_pipeline.AudioSettings(is_vad_enabled=is_vad_enabled),
            start_stage=assist_pipeline.PipelineStage.STT,
            end_stage=assist_pipeline.PipelineStage.STT,
        )
    return events


@pytest.mark.usefixtures("init_components")
async def test_the_pipeline_depends_on_the_integration_that_owns_the_app(
    hass: HomeAssistant,
) -> None:
    """Test voice_support is set up wherever the pipeline is.

    It decides whether there is an app at all, so it has to be there before
    there is anything to ask.
    """
    assert "voice_support" in hass.config.components


# ----------------------------------------------------------------------
# The wake word


@pytest.mark.usefixtures("init_components")
async def test_accepted_runs_the_pipeline(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test an accepted wake word runs the pipeline as usual."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient([(0, WakeWordAccepted(MS_PER_CHUNK))]),
    )

    assert [event.type for event in events] == [
        PipelineEventType.RUN_START,
        PipelineEventType.WAKE_WORD_END,
        PipelineEventType.STT_START,
        PipelineEventType.STT_END,
        PipelineEventType.RUN_END,
    ]
    # Speech-to-text hears the command and nothing of the wake word
    assert b"".join(mock_stt_provider_entity.received) == COMMAND


@pytest.mark.usefixtures("init_components", "mock_stt_provider_entity")
async def test_the_provider_hears_the_whole_run(hass: HomeAssistant) -> None:
    """Test it is given the wake word audio too, not only the command."""
    run = MockRun([(0, WakeWordAccepted(MS_PER_CHUNK))])

    await _async_run_pipeline(
        hass, _audio_stream(WAKE, COMMAND), client=MockClient(run=run)
    )

    assert bytes(run.audio) == WAKE + COMMAND
    assert run.audio_ended
    assert run.closed


@pytest.mark.usefixtures("init_components")
async def test_rejected_ends_the_run(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test a refused wake word ends the run with the provider's reason."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient([(0, WakeWordRejected(reason="last"))]),
    )

    assert [event.type for event in events] == [
        PipelineEventType.RUN_START,
        PipelineEventType.WAKE_WORD_REJECTED,
        PipelineEventType.RUN_END,
    ]
    assert events[1].data == {
        "wake_word_output": {
            "wake_word_phrase": PHRASE,
            "wake_word_audio_ms": MS_PER_CHUNK,
            "reason": "last",
        }
    }
    assert not mock_stt_provider_entity.received


@pytest.mark.usefixtures("init_components", "mock_stt_provider_entity")
async def test_rejection_leaves_no_cooldown(hass: HomeAssistant) -> None:
    """Test a refused wake word does not make the next one a duplicate.

    Accepting starts the cooldown that rejects the next one, so the app has
    to be asked before anything is accepted.
    """
    rejected = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient([(0, WakeWordRejected(reason="last"))]),
    )
    assert rejected[1].type is PipelineEventType.WAKE_WORD_REJECTED

    accepted = await _async_run_pipeline(hass, _audio_stream(WAKE, COMMAND))
    assert accepted[1].type is PipelineEventType.WAKE_WORD_END


@pytest.mark.usefixtures("init_components")
async def test_the_provider_moves_the_split(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test speech-to-text starts where the provider found the wake word ending."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, WORD, COMMAND),
        client=MockClient([(0, WakeWordAccepted(2 * MS_PER_CHUNK))]),
    )

    assert events[1].type is PipelineEventType.WAKE_WORD_END
    # The detection said the wake word was one chunk; the provider said two
    assert events[1].data["wake_word_output"]["wake_word_audio_ms"] == (
        2 * MS_PER_CHUNK
    )
    assert b"".join(mock_stt_provider_entity.received) == COMMAND


@pytest.mark.usefixtures("init_components")
async def test_a_verdict_can_wait_for_more_of_the_run(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test an app that answers only after hearing past the detection.

    Audio keeps being fed until the verdict comes, rather than the app
    having to ask for it.
    """
    run = MockRun([(2, WakeWordAccepted(MS_PER_CHUNK))])

    await _async_run_pipeline(
        hass, _audio_stream(WAKE, TAIL, COMMAND), client=MockClient(run=run)
    )

    assert bytes(run.audio) == WAKE + TAIL + COMMAND
    # Hearing further in does not take that audio from speech-to-text
    assert b"".join(mock_stt_provider_entity.received) == TAIL + COMMAND


@pytest.mark.usefixtures("init_components")
async def test_a_wake_word_it_does_not_know_is_never_delayed(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the run is still watched, but the detection is not second-guessed."""
    run = MockRun([])

    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient(phrases=set(), run=run),
    )

    assert events[1].type is PipelineEventType.WAKE_WORD_END
    assert b"".join(mock_stt_provider_entity.received) == COMMAND
    assert bytes(run.audio) == WAKE + COMMAND


@pytest.mark.usefixtures("init_components")
async def test_a_provider_that_says_nothing_leaves_the_detection_alone(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test a provider with no verdict by the end of the audio."""
    events = await _async_run_pipeline(
        hass, _audio_stream(WAKE, COMMAND), client=MockClient([])
    )

    assert events[1].type is PipelineEventType.WAKE_WORD_END
    assert b"".join(mock_stt_provider_entity.received) == COMMAND


@pytest.mark.usefixtures("init_components")
async def test_no_provider_is_the_pipeline_as_it_was(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test nothing registered leaves the stream exactly as it was."""
    events = await _async_run_pipeline(hass, _audio_stream(WAKE, COMMAND))

    assert events[1].type is PipelineEventType.WAKE_WORD_END
    assert b"".join(mock_stt_provider_entity.received) == COMMAND


# ----------------------------------------------------------------------
# The end of the command


@pytest.mark.usefixtures("init_components", "mock_stt_provider_entity")
async def test_the_provider_says_where_the_command_begins_and_ends(
    hass: HomeAssistant,
) -> None:
    """Test speech boundaries come back as the events satellites animate on."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND, COMMAND, COMMAND, COMMAND, COMMAND),
        is_vad_enabled=True,
        client=MockClient(
            [
                (0, WakeWordAccepted(MS_PER_CHUNK)),
                (2, SpeechStarted(timestamp_ms=20)),
                (4, SpeechEnded(timestamp_ms=40)),
            ]
        ),
    )

    assert [event.type for event in events] == [
        PipelineEventType.RUN_START,
        PipelineEventType.WAKE_WORD_END,
        PipelineEventType.STT_START,
        PipelineEventType.STT_VAD_START,
        PipelineEventType.STT_VAD_END,
        PipelineEventType.STT_END,
        PipelineEventType.RUN_END,
    ]
    assert events[3].data == {"timestamp": 20}
    assert events[4].data == {"timestamp": 40}


@pytest.mark.usefixtures("init_components")
async def test_its_last_word_arrives_with_its_departure(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the end of the command is honoured even as the app goes.

    The app says where the command ended and closes straight afterwards, so
    both land before the pipeline looks again. Reading whether it is still
    there first would throw away the thing it was waiting for, and leave the
    command to a segmenter that never heard the speech.
    """
    run = MockRun([(0, WakeWordAccepted(MS_PER_CHUNK))])

    async def _stream() -> AsyncGenerator[bytes]:
        yield WAKE
        for _ in range(3):
            yield COMMAND
        run.speech_ended_ms = 30
        run.stop_listening()
        for _ in range(3):
            yield TAIL

    events = await _async_run_pipeline(
        hass, _stream(), is_vad_enabled=True, client=MockClient(run=run)
    )

    assert [event.type for event in events].count(PipelineEventType.STT_VAD_END) == 1
    assert events[-3].data == {"timestamp": 30}
    # And nothing after the boundary reaches speech-to-text
    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 3


@pytest.mark.usefixtures("init_components")
async def test_an_app_that_goes_without_saying_leaves_it_to_the_segmenter(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the command is not cut short when the app said nothing.

    It must not leave one that never ends either: Home Assistant's own
    segmenter is already built and takes over from here.
    """
    run = MockRun([(0, WakeWordAccepted(MS_PER_CHUNK))])

    async def _stream() -> AsyncGenerator[bytes]:
        yield WAKE
        for _ in range(3):
            yield COMMAND
        run.stop_listening()
        for _ in range(3):
            yield TAIL

    events = await _async_run_pipeline(
        hass, _stream(), is_vad_enabled=True, client=MockClient(run=run)
    )

    assert PipelineEventType.STT_VAD_END not in [event.type for event in events]
    assert b"".join(mock_stt_provider_entity.received) == (COMMAND * 3) + (TAIL * 3)
