"""Tests for webrtcvad voice command segmenter."""
from unittest.mock import patch

from homeassistant.components.assist_pipeline.vad import VoiceCommandSegmenter

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
