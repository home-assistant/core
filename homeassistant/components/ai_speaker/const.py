"""Constants for AI-Speaker component."""
import logging

DOMAIN = "ai_speaker"
AIS_WS_PODCAST_URL = "https://powiedz.co/ords/dom/dom/audio_type?nature=Podcast"
AIS_WS_RADIO_URL = ""
AIS_WS_AUDIOBOOKS_URL = "https://wolnelektury.pl/api/audiobooks/?format=json"
AIS_WS_COMMAND_URL = "{ais_url}/command"
AIS_WS_TTS_URL = "{ais_url}/text_to_speech"
_LOGGER = logging.getLogger(".")
