import unittest

class TestVoiceProcessing(unittest.TestCase):
    def test_process_voice_input_fails(self):
        audio = "invalid_file.wav"
        result = process_voice_input(audio)
        self.assertIsNone(result)
