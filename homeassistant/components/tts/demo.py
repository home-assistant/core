"""
Support for the demo speech service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/demo/
"""
import os

from homeassistant.components.tts import Provider


def get_engine(hass, config):
    """Setup Demo speech component."""
    return DemoProvider()


class DemoProvider(Provider):
    """Demo speech api provider."""

    def get_tts_audio(self, message):
        """Load TTS from demo."""
        filename = os.path.join(os.path.dirname(__file__), "demo.mp3")
        try:
            with open(filename, 'rb') as voice:
                data = voice.read()
        except OSError:
            return

        return ("mp3", data)
