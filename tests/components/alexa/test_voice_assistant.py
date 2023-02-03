import unittest
from homeassistant.components.voice_assistant import identify_intent

class TestVoiceProcessing(unittest.TestCase):
    def test_identify_intent(self):
        # Test input "turn on the lights" returns "turn_on_lights"
        self.assertEqual(identify_intent("turn on the lights"), "turn_on_lights")

        # Test input "play music" returns "play_music"
        self.assertEqual(identify_intent("play music"), "play_music")

        # Test input "stop music" returns "stop_music"
        self.assertEqual(identify_intent("stop music"), "stop_music")

        # Test input "change the temperature to 25 degrees" returns "change_temperature"
        self.assertEqual(identify_intent("change the temperature to 25 degrees"), "change_temperature")

        # Test input "lock the front door" returns "lock_door"
        self.assertEqual(identify_intent("lock the front door"), "lock_door")

        # Test input "what is the weather like today?" returns "get_weather"
        self.assertEqual(identify_intent("what is the weather like today?"), "get_weather")
