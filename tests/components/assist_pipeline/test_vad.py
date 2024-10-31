"""Tests for voice command segmenter."""

import itertools as it

from homeassistant.components.assist_pipeline.vad import (
    AudioBuffer,
    VoiceCommandSegmenter,
    chunk_samples,
)

_ONE_SECOND = 1.0


def test_silence() -> None:
    """Test that 3 seconds of silence does not trigger a voice command."""
    segmenter = VoiceCommandSegmenter()

    # True return value indicates voice command has not finished
    assert segmenter.process(_ONE_SECOND * 3, False)
    assert not segmenter.in_command


def test_speech() -> None:
    """Test that silence + speech + silence triggers a voice command."""

    segmenter = VoiceCommandSegmenter()

    # silence
    assert segmenter.process(_ONE_SECOND, False)

    # "speech"
    assert segmenter.process(_ONE_SECOND, True)
    assert segmenter.in_command

    # silence
    # False return value indicates voice command is finished
    assert not segmenter.process(_ONE_SECOND, False)
    assert not segmenter.in_command


def test_audio_buffer() -> None:
    """Test audio buffer wrapping."""

    samples_per_chunk = 160  # 10 ms
    bytes_per_chunk = samples_per_chunk * 2
    leftover_buffer = AudioBuffer(bytes_per_chunk)

    # Partially fill audio buffer
    half_chunk = bytes(it.islice(it.cycle(range(256)), bytes_per_chunk // 2))
    chunks = list(chunk_samples(half_chunk, bytes_per_chunk, leftover_buffer))

    assert not chunks
    assert leftover_buffer.bytes() == half_chunk

    # Fill and wrap with 1/4 chunk left over
    three_quarters_chunk = bytes(
        it.islice(it.cycle(range(256)), int(0.75 * bytes_per_chunk))
    )
    chunks = list(chunk_samples(three_quarters_chunk, bytes_per_chunk, leftover_buffer))

    assert len(chunks) == 1
    assert (
        leftover_buffer.bytes()
        == three_quarters_chunk[len(three_quarters_chunk) - (bytes_per_chunk // 4) :]
    )
    assert chunks[0] == half_chunk + three_quarters_chunk[: bytes_per_chunk // 2]

    # Run 2 chunks through
    leftover_buffer.clear()
    assert len(leftover_buffer) == 0

    two_chunks = bytes(it.islice(it.cycle(range(256)), bytes_per_chunk * 2))
    chunks = list(chunk_samples(two_chunks, bytes_per_chunk, leftover_buffer))

    assert len(chunks) == 2
    assert len(leftover_buffer) == 0
    assert chunks[0] == two_chunks[:bytes_per_chunk]
    assert chunks[1] == two_chunks[bytes_per_chunk:]


def test_partial_chunk() -> None:
    """Test that chunk_samples returns when given a partial chunk."""
    bytes_per_chunk = 5
    samples = bytes([1, 2, 3])
    leftover_chunk_buffer = AudioBuffer(bytes_per_chunk)
    chunks = list(chunk_samples(samples, bytes_per_chunk, leftover_chunk_buffer))

    assert len(chunks) == 0
    assert leftover_chunk_buffer.bytes() == samples


def test_chunk_samples_leftover() -> None:
    """Test that chunk_samples property keeps left over bytes across calls."""
    bytes_per_chunk = 5
    samples = bytes([1, 2, 3, 4, 5, 6])
    leftover_chunk_buffer = AudioBuffer(bytes_per_chunk)
    chunks = list(chunk_samples(samples, bytes_per_chunk, leftover_chunk_buffer))

    assert len(chunks) == 1
    assert leftover_chunk_buffer.bytes() == bytes([6])

    # Add some more to the chunk
    chunks = list(chunk_samples(samples, bytes_per_chunk, leftover_chunk_buffer))

    assert len(chunks) == 1
    assert leftover_chunk_buffer.bytes() == bytes([5, 6])


def test_silence_seconds() -> None:
    """Test end of voice command silence seconds."""

    segmenter = VoiceCommandSegmenter(silence_seconds=1.0)

    # silence
    assert segmenter.process(_ONE_SECOND, False)
    assert not segmenter.in_command

    # "speech"
    assert segmenter.process(_ONE_SECOND, True)
    assert segmenter.in_command

    # not enough silence to end
    assert segmenter.process(_ONE_SECOND * 0.5, False)
    assert segmenter.in_command

    # exactly enough silence now
    assert not segmenter.process(_ONE_SECOND * 0.5, False)
    assert not segmenter.in_command


def test_silence_reset() -> None:
    """Test that speech resets end of voice command detection."""

    segmenter = VoiceCommandSegmenter(silence_seconds=1.0, reset_seconds=0.5)

    # silence
    assert segmenter.process(_ONE_SECOND, False)
    assert not segmenter.in_command

    # "speech"
    assert segmenter.process(_ONE_SECOND, True)
    assert segmenter.in_command

    # not enough silence to end
    assert segmenter.process(_ONE_SECOND * 0.5, False)
    assert segmenter.in_command

    # speech should reset silence detection
    assert segmenter.process(_ONE_SECOND * 0.5, True)
    assert segmenter.in_command

    # not enough silence to end
    assert segmenter.process(_ONE_SECOND * 0.5, False)
    assert segmenter.in_command

    # exactly enough silence now
    assert not segmenter.process(_ONE_SECOND * 0.5, False)
    assert not segmenter.in_command


def test_speech_reset() -> None:
    """Test that silence resets start of voice command detection."""

    segmenter = VoiceCommandSegmenter(
        silence_seconds=1.0, reset_seconds=0.5, speech_seconds=1.0
    )

    # silence
    assert segmenter.process(_ONE_SECOND, False)
    assert not segmenter.in_command

    # not enough speech to start voice command
    assert segmenter.process(_ONE_SECOND * 0.5, True)
    assert not segmenter.in_command

    # silence should reset speech detection
    assert segmenter.process(_ONE_SECOND, False)
    assert not segmenter.in_command

    # not enough speech to start voice command
    assert segmenter.process(_ONE_SECOND * 0.5, True)
    assert not segmenter.in_command

    # exactly enough speech now
    assert segmenter.process(_ONE_SECOND * 0.5, True)
    assert segmenter.in_command


def test_timeout() -> None:
    """Test that voice command detection times out."""

    segmenter = VoiceCommandSegmenter(timeout_seconds=1.0)

    # not enough to time out
    assert not segmenter.timed_out
    assert segmenter.process(_ONE_SECOND * 0.5, False)
    assert not segmenter.timed_out

    # enough to time out
    assert not segmenter.process(_ONE_SECOND * 0.5, True)
    assert segmenter.timed_out

    # flag resets with more audio
    assert segmenter.process(_ONE_SECOND * 0.5, True)
    assert not segmenter.timed_out

    assert not segmenter.process(_ONE_SECOND * 0.5, False)
    assert segmenter.timed_out


def test_command_seconds() -> None:
    """Test minimum number of seconds for voice command."""

    segmenter = VoiceCommandSegmenter(
        command_seconds=3, speech_seconds=1, silence_seconds=1, reset_seconds=1
    )

    assert segmenter.process(_ONE_SECOND, True)

    # Silence counts towards total command length
    assert segmenter.process(_ONE_SECOND * 0.5, False)

    # Enough to finish command now
    assert segmenter.process(_ONE_SECOND, True)
    assert segmenter.process(_ONE_SECOND * 0.5, False)

    # Silence to finish
    assert not segmenter.process(_ONE_SECOND * 0.5, False)
