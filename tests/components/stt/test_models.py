"""Test STT models."""

import pytest

from homeassistant.components.stt import SpeechAudioProcessing


def test_speech_audio_processing_default() -> None:
    """Test SpeechAudioProcessing with default values."""
    processing = SpeechAudioProcessing(
        requires_external_vad=True,
        prefers_auto_gain_enabled=True,
        prefers_noise_reduction_enabled=True,
    )

    assert processing.requires_external_vad is True
    assert processing.prefers_auto_gain_enabled is True
    assert processing.prefers_noise_reduction_enabled is True


def test_speech_audio_processing_minimal() -> None:
    """Test SpeechAudioProcessing with minimal values."""
    processing = SpeechAudioProcessing(
        requires_external_vad=False,
        prefers_auto_gain_enabled=False,
        prefers_noise_reduction_enabled=False,
    )

    assert processing.requires_external_vad is False
    assert processing.prefers_auto_gain_enabled is False
    assert processing.prefers_noise_reduction_enabled is False


def test_speech_audio_processing_mixed() -> None:
    """Test SpeechAudioProcessing with mixed values."""
    processing = SpeechAudioProcessing(
        requires_external_vad=True,
        prefers_auto_gain_enabled=False,
        prefers_noise_reduction_enabled=True,
    )

    assert processing.requires_external_vad is True
    assert processing.prefers_auto_gain_enabled is False
    assert processing.prefers_noise_reduction_enabled is True


@pytest.mark.parametrize(
    (
        "requires_external_vad",
        "prefers_auto_gain_enabled",
        "prefers_noise_reduction_enabled",
    ),
    [
        (True, True, True),
        (True, True, False),
        (True, False, True),
        (True, False, False),
        (False, True, True),
        (False, True, False),
        (False, False, True),
        (False, False, False),
    ],
)
def test_speech_audio_processing_parametrized(
    requires_external_vad: bool,
    prefers_auto_gain_enabled: bool,
    prefers_noise_reduction_enabled: bool,
) -> None:
    """Test SpeechAudioProcessing with various parameter combinations."""
    processing = SpeechAudioProcessing(
        requires_external_vad=requires_external_vad,
        prefers_auto_gain_enabled=prefers_auto_gain_enabled,
        prefers_noise_reduction_enabled=prefers_noise_reduction_enabled,
    )

    assert processing.requires_external_vad == requires_external_vad
    assert processing.prefers_auto_gain_enabled == prefers_auto_gain_enabled
    assert processing.prefers_noise_reduction_enabled == prefers_noise_reduction_enabled
