"""Constants for the Testing of the Fish Audio text-to-speech integration."""

from unittest.mock import MagicMock

from fishaudio.types import Voice
from fishaudio.types.account import Credits

MOCK_VOICE_1 = MagicMock(spec=Voice)
MOCK_VOICE_1.id = "voice-alpha"
MOCK_VOICE_1.title = "Alpha Voice"
MOCK_VOICE_1.languages = ["en", "es"]
MOCK_VOICE_1.task_count = 1000

MOCK_VOICE_2 = MagicMock(spec=Voice)
MOCK_VOICE_2.id = "voice-beta"
MOCK_VOICE_2.title = "Beta Voice"
MOCK_VOICE_2.languages = ["en", "zh"]
MOCK_VOICE_2.task_count = 500

MOCK_VOICES = [MOCK_VOICE_1, MOCK_VOICE_2]

MOCK_CREDITS = MagicMock(spec=Credits)
MOCK_CREDITS.user_id = "test_user"
