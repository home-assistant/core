"""Tests for webrtcvad voice command segmenter."""
import itertools as it
from unittest.mock import patch

import pytest

from homeassistant.components.assist_pipeline.vad import (
    AudioBuffer,
    VoiceCommandSegmenter,
)

_ONE_SECOND = 16000 * 2  # 16Khz 16-bit


def test_silence() -> None:
    """Test that 3 seconds of silence does not trigger a voice command."""
    segmenter = VoiceCommandSegmenter()

    # True return value indicates voice command has not finished
    assert segmenter.process(bytes(_ONE_SECOND * 3))


def test_speech() -> None:
    """Test that silence + speech + silence triggers a voice command."""

    def is_speech(self, chunk, sample_rate):
        """Anything non-zero is speech."""
        return sum(chunk) > 0

    with patch(
        "webrtcvad.Vad.is_speech",
        new=is_speech,
    ):
        segmenter = VoiceCommandSegmenter()

        # silence
        assert segmenter.process(bytes(_ONE_SECOND))

        # "speech"
        assert segmenter.process(bytes([255] * _ONE_SECOND))

        # silence
        # False return value indicates voice command is finished
        assert not segmenter.process(bytes(_ONE_SECOND))


def test_audio_buffer() -> None:
    """Test audio buffer wrapping."""

    def is_speech(self, chunk, sample_rate):
        """Disable VAD."""
        return False

    with patch(
        "webrtcvad.Vad.is_speech",
        new=is_speech,
    ):
        segmenter = VoiceCommandSegmenter()
        bytes_per_chunk = segmenter.vad_samples_per_chunk * 2

        with patch.object(
            segmenter, "_process_chunk", return_value=True
        ) as mock_process:
            # Partially fill audio buffer
            half_chunk = bytes(it.islice(it.cycle(range(256)), bytes_per_chunk // 2))
            segmenter.process(half_chunk)

            assert not mock_process.called
            assert segmenter.audio_buffer == half_chunk

            # Fill and wrap with 1/4 chunk left over
            three_quarters_chunk = bytes(
                it.islice(it.cycle(range(256)), int(0.75 * bytes_per_chunk))
            )
            segmenter.process(three_quarters_chunk)

            assert mock_process.call_count == 1
            assert (
                segmenter.audio_buffer
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
            assert len(segmenter.audio_buffer) == 0

            mock_process.reset_mock()
            two_chunks = bytes(it.islice(it.cycle(range(256)), bytes_per_chunk * 2))
            segmenter.process(two_chunks)

            assert mock_process.call_count == 2
            assert len(segmenter.audio_buffer) == 0
            assert mock_process.call_args_list[0][0][0] == two_chunks[:bytes_per_chunk]
            assert mock_process.call_args_list[1][0][0] == two_chunks[bytes_per_chunk:]


def test_audio_buffer_errors() -> None:
    """Test audio buffer errors."""
    audio_buffer = AudioBuffer(1)

    with pytest.raises(ValueError):
        audio_buffer.length = 2

    with pytest.raises(ValueError):
        audio_buffer.length = -2
