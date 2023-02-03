import unittest
from homeassistant.components.voice_assistant import identify_intent

class TestVoiceProcessing(unittest.TestCase):
    def test_identify_intent(self):
        self.assertEqual(identify_intent("turn on the lights"), "turn_on_lights")
        self.assertEqual(identify_intent("play music"), "play_music")
        self.assertEqual(identify_intent("stop music"), "stop_music")
        self.assertEqual(identify_intent("set the temperature to 72 degrees"), "set_temperature")

    def test_process_voice_input(self):
        process_voice_input("turn on the lights")
        self.assertTrue(lights_are_on())
        
        process_voice_input("play music")
        self.assertTrue(music_is_playing())
        
        process_voice_input("stop music")
        self.assertFalse(music_is_playing())
        
        process_voice_input("set the temperature to 72 degrees")
        self.assertEqual(get_temperature(), 72)

def identify_intent(voice_input):
    intents = {
        "turn_on_lights": ["turn", "on", "the", "lights"],
        "play_music": ["play", "music"],
        "stop_music": ["stop", "music"],
    }
    
    words = voice_input.split()
    for intent, keywords in intents.items():
        if all(word in words for word in keywords):
            return intent
    return None
