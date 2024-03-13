"""Tests for voice command segmenter."""

import itertools as it
from unittest.mock import patch

from homeassistant.components.assist_pipeline.vad import (
    AudioBuffer,
    VoiceActivityDetector,
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

    class DisabledVad(VoiceActivityDetector):
        def is_speech(self, chunk):
            return False

        @property
        def samples_per_chunk(self):
            return 160  # 10 ms

    vad = DisabledVad()
    bytes_per_chunk = vad.samples_per_chunk * 2
    vad_buffer = AudioBuffer(bytes_per_chunk)
    segmenter = VoiceCommandSegmenter()

    with patch.object(vad, "is_speech", return_value=False) as mock_process:
        # Partially fill audio buffer
        half_chunk = bytes(it.islice(it.cycle(range(256)), bytes_per_chunk // 2))
        segmenter.process_with_vad(half_chunk, vad, vad_buffer)

        assert not mock_process.called
        assert vad_buffer is not None
        assert vad_buffer.bytes() == half_chunk

        # Fill and wrap with 1/4 chunk left over
        three_quarters_chunk = bytes(
            it.islice(it.cycle(range(256)), int(0.75 * bytes_per_chunk))
        )
        segmenter.process_with_vad(three_quarters_chunk, vad, vad_buffer)

        assert mock_process.call_count == 1
        assert (
            vad_buffer.bytes()
            == three_quarters_chunk[
                len(three_quarters_chunk) - (bytes_per_chunk // 4) :
            ]
        )
        assert (
            mock_process.call_args[0][0]
            == half_chunk + three_quarters_chunk[: bytes_per_chunk // 2]
        )

        # Run 2 chunks through
        segmenter.reset()
        vad_buffer.clear()
        assert len(vad_buffer) == 0

        mock_process.reset_mock()
        two_chunks = bytes(it.islice(it.cycle(range(256)), bytes_per_chunk * 2))
        segmenter.process_with_vad(two_chunks, vad, vad_buffer)

        assert mock_process.call_count == 2
        assert len(vad_buffer) == 0
        assert mock_process.call_args_list[0][0][0] == two_chunks[:bytes_per_chunk]
        assert mock_process.call_args_list[1][0][0] == two_chunks[bytes_per_chunk:]


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


def test_vad_no_chunking() -> None:
    """Test VAD that doesn't require chunking."""

    class VadNoChunk(VoiceActivityDetector):
        def is_speech(self, chunk: bytes) -> bool:
            return sum(chunk) > 0

        @property
        def samples_per_chunk(self) -> int | None:
            return None

    vad = VadNoChunk()
    segmenter = VoiceCommandSegmenter(
        speech_seconds=1.0, silence_seconds=1.0, reset_seconds=0.5
    )
    silence = bytes([0] * 16000)
    speech = bytes([255] * (16000 // 2))

    # Test with differently-sized chunks
    assert vad.is_speech(speech)
    assert not vad.is_speech(silence)

    # Simulate voice command
    assert segmenter.process_with_vad(silence, vad, None)
    # begin
    assert segmenter.process_with_vad(speech, vad, None)
    assert segmenter.process_with_vad(speech, vad, None)
    assert segmenter.process_with_vad(speech, vad, None)
    # reset with silence
    assert segmenter.process_with_vad(silence, vad, None)
    # resume
    assert segmenter.process_with_vad(speech, vad, None)
    assert segmenter.process_with_vad(speech, vad, None)
    assert segmenter.process_with_vad(speech, vad, None)
    assert segmenter.process_with_vad(speech, vad, None)
    # end
    assert segmenter.process_with_vad(silence, vad, None)
    assert not segmenter.process_with_vad(silence, vad, None)
