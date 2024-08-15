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


def test_speech() -> None:
    """Test that silence + speech + silence triggers a voice command."""

    def is_speech(chunk):
        """Anything non-zero is speech."""
        return sum(chunk) > 0

    segmenter = VoiceCommandSegmenter()

    # silence
    assert segmenter.process(_ONE_SECOND, False)

    # "speech"
    assert segmenter.process(_ONE_SECOND, True)

    # silence
    # False return value indicates voice command is finished
    assert not segmenter.process(_ONE_SECOND, False)


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
