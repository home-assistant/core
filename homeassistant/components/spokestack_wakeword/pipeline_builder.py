"""Spokestack SpeechPipeline Builder."""
from spokestack.activation_timeout import ActivationTimeout
from spokestack.pipeline import SpeechPipeline
from spokestack.vad.webrtc import VoiceActivityDetector

from .const import SAVE_PATH


def build_pipeline() -> SpeechPipeline:
    """Build SpeechPipeline for wake word detection."""
    from spokestack.io.pyaudio import (  # pylint: disable=import-outside-toplevel
        PyAudioInput,
    )
    from spokestack.wakeword.tflite import (  # pylint: disable=import-outside-toplevel
        WakewordTrigger,
    )

    return SpeechPipeline(
        PyAudioInput(sample_rate=16000, frame_width=20, exception_on_overflow=False),
        [
            VoiceActivityDetector(frame_width=20, vad_fall=500),
            WakewordTrigger(
                pre_emphasis=0.97,
                model_dir=SAVE_PATH,
            ),
            ActivationTimeout(),
        ],
    )
