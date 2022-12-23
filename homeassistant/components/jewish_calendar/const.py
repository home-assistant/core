"""Constants for the Jewish Calendar integration."""
from typing import Final

DOMAIN: Final = "jewish_calendar"

CONF_DIASPORA: Final = "diaspora"
CONF_CANDLE_LIGHT_MINUTES: Final = "candle_lighting_minutes_before_sunset"
CONF_HAVDALAH_OFFSET_MINUTES: Final = "havdalah_minutes_after_sunset"

DEFAULT_NAME: Final = "Jewish Calendar"
DEFAULT_CANDLE_LIGHT: Final = 18
DEFAULT_DIASPORA: Final = False
DEFAULT_HAVDALAH_OFFSET_MINUTES: Final = 0
DEFAULT_LANGUAGE: Final = "english"
