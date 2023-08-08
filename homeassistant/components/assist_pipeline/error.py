"""Assist pipeline errors."""

from homeassistant.exceptions import HomeAssistantError


class PipelineError(HomeAssistantError):
    """Base class for pipeline errors."""

    def __init__(self, code: str, message: str) -> None:
        """Set error message."""
        self.code = code
        self.message = message

        super().__init__(f"Pipeline error code={code}, message={message}")


class PipelineNotFound(PipelineError):
    """Unspecified pipeline picked."""


class WakeWordDetectionError(PipelineError):
    """Error in wake-word-detection portion of pipeline."""


class WakeWordTimeoutError(WakeWordDetectionError):
    """Timeout when wake word was not detected."""


class SpeechToTextError(PipelineError):
    """Error in speech-to-text portion of pipeline."""


class IntentRecognitionError(PipelineError):
    """Error in intent recognition portion of pipeline."""


class TextToSpeechError(PipelineError):
    """Error in text-to-speech portion of pipeline."""
