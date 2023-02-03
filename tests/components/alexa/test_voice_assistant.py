import pytest
from homeassistant.components.voice_assistant import process_voice_input
from homeassistant.core import HomeAssistant
from typing import ParamSpec

class TestVoiceProcessing(unittest.TestCase):
    def test_identify_intent(self):
    # Test input "turn on the lights" returns "turn_on_lights"
    self.assertEqual(identify_intent("turn on the lights"), "turn_on_lights")

    # Test input "play music" returns "play_music"
    self.assertEqual(identify_intent("play music"), "play_music")

    # Add more tests as necessary to cover additional functionality
    # Test input "stop music" returns "stop_music"
    self.assertEqual(identify_intent("stop music"), "stop_music")
