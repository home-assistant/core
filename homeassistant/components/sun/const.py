"""Constants for the Sun integration."""
from typing import Final

DOMAIN: Final = "sun"

DEFAULT_NAME: Final = "Sun"

SIGNAL_POSITION_CHANGED = f"{DOMAIN}_position_changed"
SIGNAL_EVENTS_CHANGED = f"{DOMAIN}_events_changed"
