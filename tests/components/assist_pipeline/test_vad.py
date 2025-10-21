"""Tests for voice command segmenter."""

import itertools as it

from homeassistant.components.assist_pipeline.vad import (
    AudioBuffer,
    VadSensitivity,
    VoiceActivityTimeout,
    VoiceCommandSegmenter,
    chunk_samples,
)

_ONE_SECOND = 1.0


def test_silence() -> None:
    """Test that 3 seconds of silence does not trigger a voice command."""
    segmenter = VoiceCommandSegmenter()

    # True return value indicates voice command has not finished
    assert segmenter.process(_ONE_SECOND * 3, 0.0)
    assert not segmenter.in_command


def test_speech() -> None:
    """Test that silence + speech + silence triggers a voice command."""

    segmenter = VoiceCommandSegmenter()

    # silence
    assert segmenter.process(_ONE_SECOND, 0.0)

    # "speech"
    assert segmenter.process(_ONE_SECOND, 1.0)
    assert segmenter.in_command

    # silence
    # False return value indicates voice command is finished
    assert not segmenter.process(_ONE_SECOND, 0.0)
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
    assert segmenter.process(_ONE_SECOND, 0.0)
    assert not segmenter.in_command

    # "speech"
    assert segmenter.process(_ONE_SECOND, 1.0)
    assert segmenter.in_command

    # not enough silence to end
    assert segmenter.process(_ONE_SECOND * 0.5, 0.0)
    assert segmenter.in_command

    # exactly enough silence now
    assert not segmenter.process(_ONE_SECOND * 0.5, 0.0)
    assert not segmenter.in_command


def test_silence_reset() -> None:
    """Test that speech resets end of voice command detection."""

    segmenter = VoiceCommandSegmenter(silence_seconds=1.0, reset_seconds=0.5)

    # silence
    assert segmenter.process(_ONE_SECOND, 0.0)
    assert not segmenter.in_command

    # "speech"
    assert segmenter.process(_ONE_SECOND, 1.0)
    assert segmenter.in_command

    # not enough silence to end
    assert segmenter.process(_ONE_SECOND * 0.5, 0.0)
    assert segmenter.in_command

    # speech should reset silence detection
    assert segmenter.process(_ONE_SECOND * 0.5, 1.0)
    assert segmenter.in_command

    # not enough silence to end
    assert segmenter.process(_ONE_SECOND * 0.5, 0.0)
    assert segmenter.in_command

    # exactly enough silence now
    assert not segmenter.process(_ONE_SECOND * 0.5, 0.0)
    assert not segmenter.in_command


def test_speech_reset() -> None:
    """Test that silence resets start of voice command detection."""

    segmenter = VoiceCommandSegmenter(
        silence_seconds=1.0, reset_seconds=0.5, speech_seconds=1.0
    )

    # silence
    assert segmenter.process(_ONE_SECOND, 0.0)
    assert not segmenter.in_command

    # not enough speech to start voice command
    assert segmenter.process(_ONE_SECOND * 0.5, 1.0)
    assert not segmenter.in_command

    # silence should reset speech detection
    assert segmenter.process(_ONE_SECOND, 0.0)
    assert not segmenter.in_command

    # not enough speech to start voice command
    assert segmenter.process(_ONE_SECOND * 0.5, 1.0)
    assert not segmenter.in_command

    # exactly enough speech now
    assert segmenter.process(_ONE_SECOND * 0.5, 1.0)
    assert segmenter.in_command


def test_timeout() -> None:
    """Test that voice command detection times out."""

    segmenter = VoiceCommandSegmenter(timeout_seconds=1.0)

    # not enough to time out
    assert not segmenter.timed_out
    assert segmenter.process(_ONE_SECOND * 0.5, 0.0)
    assert not segmenter.timed_out

    # enough to time out
    assert not segmenter.process(_ONE_SECOND * 0.5, 1.0)
    assert segmenter.timed_out

    # flag resets with more audio
    assert segmenter.process(_ONE_SECOND * 0.5, 1.0)
    assert not segmenter.timed_out

    assert not segmenter.process(_ONE_SECOND * 0.5, 0.0)
    assert segmenter.timed_out


def test_command_seconds() -> None:
    """Test minimum number of seconds for voice command."""

    segmenter = VoiceCommandSegmenter(
        command_seconds=3, speech_seconds=1, silence_seconds=1, reset_seconds=1
    )

    assert segmenter.process(_ONE_SECOND, 1.0)

    # Silence counts towards total command length
    assert segmenter.process(_ONE_SECOND * 0.5, 0.0)

    # Enough to finish command now
    assert segmenter.process(_ONE_SECOND, 1.0)
    assert segmenter.process(_ONE_SECOND * 0.5, 0.0)

    # Silence to finish
    assert not segmenter.process(_ONE_SECOND * 0.5, 0.0)


def test_speech_thresholds() -> None:
    """Test before/in command speech thresholds."""

    segmenter = VoiceCommandSegmenter(
        before_command_speech_threshold=0.2,
        in_command_speech_threshold=0.5,
        command_seconds=2,
        speech_seconds=1,
        silence_seconds=1,
    )

    # Not high enough probability to trigger command
    assert segmenter.process(_ONE_SECOND, 0.1)
    assert not segmenter.in_command

    # Triggers command
    assert segmenter.process(_ONE_SECOND, 0.3)
    assert segmenter.in_command

    # Now that same probability is considered silence.
    # Finishes command.
    assert not segmenter.process(_ONE_SECOND, 0.3)


def test_vad_sensitivity_to_seconds() -> None:
    """Test VadSensitivity.to_seconds() method."""
    assert abs(VadSensitivity.to_seconds(VadSensitivity.RELAXED) - 1.25) < 0.01
    assert abs(VadSensitivity.to_seconds(VadSensitivity.AGGRESSIVE) - 0.25) < 0.01
    assert abs(VadSensitivity.to_seconds(VadSensitivity.DEFAULT) - 0.7) < 0.01
    
    # Test with string values
    assert abs(VadSensitivity.to_seconds("relaxed") - 1.25) < 0.01
    assert abs(VadSensitivity.to_seconds("aggressive") - 0.25) < 0.01
    assert abs(VadSensitivity.to_seconds("default") - 0.7) < 0.01


def test_audio_buffer_length_property() -> None:
    """Test AudioBuffer.length property."""
    buffer = AudioBuffer(10)
    assert buffer.length == 0
    
    buffer.append(b"hello")
    assert buffer.length == 5
    
    buffer.clear()
    assert buffer.length == 0


def test_audio_buffer_append_overflow() -> None:
    """Test AudioBuffer.append raises ValueError when buffer overflows."""
    buffer = AudioBuffer(5)
    
    # This should work
    buffer.append(b"hello")
    
    # This should raise ValueError
    try:
        buffer.append(b"x")  # Adding 1 more byte to 5-byte buffer should overflow
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "Length cannot be greater than buffer size" in str(e)


def test_voice_command_segmenter_reset() -> None:
    """Test VoiceCommandSegmenter.reset() method."""
    segmenter = VoiceCommandSegmenter(
        speech_seconds=2.0,
        command_seconds=3.0,
        silence_seconds=1.5,
        timeout_seconds=10.0,
        reset_seconds=0.8
    )
    
    # Modify some internal state
    segmenter.in_command = True
    segmenter.timed_out = True
    
    # Reset should restore defaults
    segmenter.reset()
    
    assert not segmenter.in_command
    assert abs(segmenter._speech_seconds_left - 2.0) < 0.01
    assert abs(segmenter._command_seconds_left - 1.0) < 0.01  # command_seconds - speech_seconds
    assert abs(segmenter._silence_seconds_left - 1.5) < 0.01
    assert abs(segmenter._timeout_seconds_left - 10.0) < 0.01
    assert abs(segmenter._reset_seconds_left - 0.8) < 0.01


def test_voice_command_segmenter_process_with_vad_no_chunking() -> None:
    """Test VoiceCommandSegmenter.process_with_vad() without chunking."""
    segmenter = VoiceCommandSegmenter()
    
    # Mock VAD function
    def mock_vad_is_speech(chunk: bytes) -> bool:
        return len(chunk) > 10  # Simple mock: speech if chunk is large
    
    # Test with small chunk (no speech)
    result = segmenter.process_with_vad(
        chunk=b"small",
        vad_samples_per_chunk=None,
        vad_is_speech=mock_vad_is_speech,
        leftover_chunk_buffer=None
    )
    assert result is True
    assert not segmenter.in_command
    
    # Test with large chunk (speech)
    result = segmenter.process_with_vad(
        chunk=b"this is a much larger chunk",
        vad_samples_per_chunk=None,
        vad_is_speech=mock_vad_is_speech,
        leftover_chunk_buffer=None
    )
    assert result is True


def test_voice_command_segmenter_process_with_vad_chunking_error() -> None:
    """Test VoiceCommandSegmenter.process_with_vad() raises error when buffer is missing."""
    segmenter = VoiceCommandSegmenter()
    
    def mock_vad_is_speech(chunk: bytes) -> bool:
        return True
    
    # Should raise ValueError when buffer is None but chunking is enabled
    try:
        segmenter.process_with_vad(
            chunk=b"test",
            vad_samples_per_chunk=160,
            vad_is_speech=mock_vad_is_speech,
            leftover_chunk_buffer=None
        )
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "leftover_chunk_buffer is required when vad uses chunking" in str(e)


def test_voice_activity_timeout() -> None:
    """Test VoiceActivityTimeout basic functionality."""
    timeout = VoiceActivityTimeout(silence_seconds=1.0, reset_seconds=0.5)
    
    # Start with silence - should not timeout yet
    assert timeout.process(0.5, 0.0)
    
    # More silence should cause timeout
    assert not timeout.process(0.6, 0.0)
    
    # Should reset after timeout
    assert abs(timeout._silence_seconds_left - 1.0) < 0.01


def test_voice_activity_timeout_speech_reset() -> None:
    """Test VoiceActivityTimeout speech resets the timeout."""
    timeout = VoiceActivityTimeout(silence_seconds=1.0, reset_seconds=0.5)
    
    # Some silence
    assert timeout.process(0.7, 0.0)
    
    # Speech should reset if long enough
    assert timeout.process(0.6, 1.0)
    assert abs(timeout._silence_seconds_left - 1.0) < 0.01
    
    # Silence again
    assert timeout.process(0.5, 0.0)
    
    # Should still be active since timeout was reset
    assert timeout.process(0.4, 0.0)


def test_voice_activity_timeout_none_speech_probability() -> None:
    """Test VoiceActivityTimeout handles None speech probability."""
    timeout = VoiceActivityTimeout(silence_seconds=0.5)
    
    # None should be treated as 0.0 (silence)
    assert timeout.process(0.3, None)
    assert not timeout.process(0.3, None)  # Should timeout
