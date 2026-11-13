"""Test the pipeline handing a satellite's audio to the Voice app."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable
from unittest.mock import patch

import pytest

from homeassistant.components import assist_pipeline, stt
from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.components.assist_pipeline.const import MS_PER_CHUNK
from homeassistant.components.voice_support import AudioRun, AudioRunRequest
from homeassistant.core import Context, HomeAssistant

from .conftest import MockSTTProviderEntity, make_10ms_chunk

from tests.components.voice_support.common import (
    Answer,
    FakeWebsocket,
    accepted,
    rejected,
    speech_ended,
    speech_started,
)

WAKE = make_10ms_chunk(b"wake")
WORD = make_10ms_chunk(b"word")
COMMAND = make_10ms_chunk(b"command")
TAIL = make_10ms_chunk(b"tail")

PHRASE = "okay nabu"


class MockClient:
    """Whatever voice_support has behind its one call, as far as the pipeline can tell.

    The run itself is real; only the app's end of it is faked.
    """

    def __init__(
        self,
        answers: list[tuple[int, Answer]] | None = None,
        *,
        phrases: set[str] | None = None,
        websocket: FakeWebsocket | None = None,
    ) -> None:
        """Set up an app with a canned run."""
        self.answers = answers or []
        self.phrases = {PHRASE} if phrases is None else phrases
        self.requests: list[AudioRunRequest] = []
        self.websocket = websocket

    async def async_start_run(
        self, hass: HomeAssistant, request: AudioRunRequest, audio: AsyncIterable[bytes]
    ) -> AudioRun:
        """Open the run."""
        self.requests.append(request)
        if self.websocket is None:
            self.websocket = FakeWebsocket(self.answers)
        return AudioRun(
            hass,
            self.websocket,  # type: ignore[arg-type]
            audio,
            verifies_wake_word=(
                (request.wake_word_audio_ms is not None)
                and (request.wake_word_phrase in self.phrases)
            ),
        )


async def _audio_stream(*chunks: bytes) -> AsyncGenerator[bytes]:
    for chunk in chunks:
        yield chunk


async def _async_run_pipeline(
    hass: HomeAssistant,
    audio_stream: AsyncIterable[bytes],
    wake_word_audio_ms: int | None = MS_PER_CHUNK,
    wake_word_phrase: str | None = PHRASE,
    is_vad_enabled: bool = False,
    client: MockClient | None = None,
) -> list[PipelineEvent]:
    """Run a pipeline with ``client`` answering voice_support's one call."""
    events: list[PipelineEvent] = []

    async def _start_run(
        hass: HomeAssistant, request: AudioRunRequest, audio: AsyncIterable[bytes]
    ) -> AudioRun | None:
        if client is None:
            return None
        return await client.async_start_run(hass, request, audio)

    with patch(
        "homeassistant.components.voice_support.async_start_run",
        side_effect=_start_run,
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
async def test_accepted_runs_the_pipeline(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test an accepted wake word runs the pipeline as usual."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient([(0, accepted(MS_PER_CHUNK))]),
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


@pytest.mark.usefixtures("init_components")
async def test_rejected_ends_the_run(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test a refused wake word ends the run with the provider's reason."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient([(0, rejected("last"))]),
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
    first = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient([(0, rejected("last"))]),
    )
    assert first[1].type is PipelineEventType.WAKE_WORD_REJECTED

    second = await _async_run_pipeline(hass, _audio_stream(WAKE, COMMAND))
    assert second[1].type is PipelineEventType.WAKE_WORD_END


@pytest.mark.usefixtures("init_components")
async def test_the_provider_moves_the_split(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test speech-to-text starts where the provider found the wake word ending."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, WORD, COMMAND),
        client=MockClient([(0, accepted(2 * MS_PER_CHUNK))]),
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
    websocket = FakeWebsocket([(2, accepted(MS_PER_CHUNK))])

    await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, TAIL, COMMAND),
        client=MockClient(websocket=websocket),
    )

    assert bytes(websocket.audio) == WAKE + TAIL + COMMAND
    # Hearing further in does not take that audio from speech-to-text
    assert b"".join(mock_stt_provider_entity.received) == TAIL + COMMAND


@pytest.mark.usefixtures("init_components")
async def test_a_wake_word_it_does_not_know_is_never_delayed(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the run is still watched, but the detection is not second-guessed."""
    websocket = FakeWebsocket([])

    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND),
        client=MockClient(phrases=set(), websocket=websocket),
    )

    assert events[1].type is PipelineEventType.WAKE_WORD_END
    assert b"".join(mock_stt_provider_entity.received) == COMMAND
    assert bytes(websocket.audio) == WAKE + COMMAND


@pytest.mark.usefixtures("init_components")
async def test_a_wake_word_not_in_the_audio_is_never_verified(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test a satellite that only names the wake word is not second-guessed."""
    websocket = FakeWebsocket([(0, rejected("last"))])

    events = await _async_run_pipeline(
        hass,
        _audio_stream(COMMAND),
        wake_word_audio_ms=None,
        is_vad_enabled=True,
        client=MockClient(websocket=websocket),
    )

    assert [event.type for event in events] == [
        PipelineEventType.RUN_START,
        PipelineEventType.STT_START,
        PipelineEventType.STT_END,
        PipelineEventType.RUN_END,
    ]
    assert b"".join(mock_stt_provider_entity.received) == COMMAND
    assert bytes(websocket.audio) == COMMAND


@pytest.mark.usefixtures("init_components")
async def test_a_provider_that_says_nothing_leaves_the_detection_alone(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test a provider with no verdict in time, while the satellite is still talking."""

    async def _stream() -> AsyncGenerator[bytes]:
        yield WAKE
        # The satellite's stream is waiting for audio when the verdict times out
        await asyncio.sleep(0.01)
        yield COMMAND

    with patch(
        "homeassistant.components.voice_support.client.WAKE_WORD_VERDICT_SECONDS", 0
    ):
        events = await _async_run_pipeline(hass, _stream(), client=MockClient([]))

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


@pytest.mark.usefixtures("init_components")
async def test_the_provider_says_where_the_command_begins_and_ends(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test speech boundaries come back as the events satellites animate on."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND, COMMAND, COMMAND, COMMAND, COMMAND),
        is_vad_enabled=True,
        client=MockClient(
            [
                (0, accepted(MS_PER_CHUNK)),
                (2, speech_started(20)),
                (4, speech_ended(40)),
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
    # Speech-to-text hears up to where the command ended, nothing after
    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 3


@pytest.mark.usefixtures("init_components")
async def test_a_provider_that_never_ends_the_command(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the command is cut off when the app never says where it ends."""
    with patch(
        "homeassistant.components.assist_pipeline.default_pipeline.RUN_COMMAND_TIMEOUT_MS",
        3 * MS_PER_CHUNK,
    ):
        events = await _async_run_pipeline(
            hass,
            _audio_stream(WAKE, COMMAND, COMMAND, COMMAND, COMMAND, COMMAND),
            is_vad_enabled=True,
            client=MockClient([(0, accepted(MS_PER_CHUNK)), (2, speech_started(20))]),
        )

    vad_ends = [
        event.data for event in events if event.type is PipelineEventType.STT_VAD_END
    ]
    assert vad_ends == [{"timestamp": 4 * MS_PER_CHUNK}]
    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 3


@pytest.mark.usefixtures("init_components")
async def test_a_provider_that_goes_away_ends_the_command_there(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the command ends where the app stopped watching the run.

    One command cut short, once, rather than a segmenter that heard none
    of it taking over mid-command.
    """
    websocket = FakeWebsocket([(0, accepted(MS_PER_CHUNK))])

    async def _stream() -> AsyncGenerator[bytes]:
        yield WAKE
        for _ in range(3):
            yield COMMAND
        websocket.go_away()
        for _ in range(3):
            yield TAIL

    events = await _async_run_pipeline(
        hass, _stream(), is_vad_enabled=True, client=MockClient(websocket=websocket)
    )

    vad_ends = [
        event.data for event in events if event.type is PipelineEventType.STT_VAD_END
    ]
    # Counted from the start of the run, the wake word chunk included
    assert vad_ends == [{"timestamp": 4 * MS_PER_CHUNK}]
    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 3


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param(
            [
                (0, accepted(MS_PER_CHUNK)),
                (0, speech_started(20)),
                (0, speech_ended(40)),
                (0, None),
            ],
            id="before_the_command",
        ),
        pytest.param(
            [
                (0, accepted(MS_PER_CHUNK)),
                (2, speech_started(20)),
                (3, speech_ended(40)),
                (3, None),
            ],
            id="mid_command",
        ),
    ],
)
@pytest.mark.usefixtures("init_components")
async def test_a_provider_that_finishes_keeps_its_boundary(
    hass: HomeAssistant,
    mock_stt_provider_entity: MockSTTProviderEntity,
    answers: list[tuple[int, Answer]],
) -> None:
    """Test an app that is done once it said where the command ends.

    Speech-to-text hears everything up to there, whether the app went
    before the command reached speech-to-text or while it was being heard.
    """
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND, COMMAND, COMMAND, COMMAND, COMMAND),
        is_vad_enabled=True,
        client=MockClient(answers),
    )

    vad_ends = [
        event.data for event in events if event.type is PipelineEventType.STT_VAD_END
    ]
    assert vad_ends == [{"timestamp": 40}]
    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 3


@pytest.mark.usefixtures("init_components")
async def test_a_boundary_at_the_end_of_the_audio(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the end of the command is still reported when no audio follows it."""
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND, COMMAND, COMMAND),
        is_vad_enabled=True,
        client=MockClient(
            [
                (0, accepted(MS_PER_CHUNK)),
                (2, speech_started(20)),
                (4, speech_ended(40)),
            ]
        ),
    )

    vad_ends = [
        event.data for event in events if event.type is PipelineEventType.STT_VAD_END
    ]
    assert vad_ends == [{"timestamp": 40}]
    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 3


@pytest.mark.usefixtures("init_components")
async def test_delayed_boundary_without_more_audio(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test an app boundary ends STT while the source waits for more audio."""
    websocket = FakeWebsocket([(0, accepted(MS_PER_CHUNK))])

    async def audio_stream() -> AsyncGenerator[bytes]:
        yield WAKE
        yield COMMAND
        yield COMMAND
        await asyncio.Event().wait()

    async def send_boundary() -> None:
        while len(mock_stt_provider_entity.received) < 2:
            await asyncio.sleep(0)
        websocket.queue_answer(speech_ended(30))

    hass.async_create_task(send_boundary())
    async with asyncio.timeout(1):
        events = await _async_run_pipeline(
            hass,
            audio_stream(),
            is_vad_enabled=True,
            client=MockClient(websocket=websocket),
        )

    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 2
    assert [
        event.data for event in events if event.type is PipelineEventType.STT_VAD_END
    ] == [{"timestamp": 30}]


@pytest.mark.usefixtures("init_components")
async def test_delayed_boundary_after_audio_end(
    hass: HomeAssistant, mock_stt_provider_entity: MockSTTProviderEntity
) -> None:
    """Test the final app response reaches STT after the source ends."""
    websocket = FakeWebsocket([(0, accepted(MS_PER_CHUNK))])

    async def send_boundary() -> None:
        while not websocket.audio_ended:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        websocket.queue_answer(speech_ended(40))
        websocket.go_away()

    hass.async_create_task(send_boundary())
    events = await _async_run_pipeline(
        hass,
        _audio_stream(WAKE, COMMAND, COMMAND, COMMAND),
        is_vad_enabled=True,
        client=MockClient(websocket=websocket),
    )

    assert b"".join(mock_stt_provider_entity.received) == COMMAND * 3
    assert [
        event.data for event in events if event.type is PipelineEventType.STT_VAD_END
    ] == [{"timestamp": 40}]
