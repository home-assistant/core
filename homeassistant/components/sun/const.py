"""Constants for the Sun integration."""

from typing import Final

import astral

DOMAIN: Final = "sun"

DEFAULT_NAME: Final = "Sun"

# Elevation of the sun's center at the horizon, in degrees. This is the value
# astral uses for sunrise/sunset (atmospheric refraction plus the sun's radius).
ELEVATION_HORIZON: Final = -0.833

# Sun elevation, in degrees, at each twilight boundary
ELEVATION_CIVIL: Final[float] = -astral.Depression.CIVIL.value
ELEVATION_NAUTICAL: Final[float] = -astral.Depression.NAUTICAL.value
ELEVATION_ASTRONOMICAL: Final[float] = -astral.Depression.ASTRONOMICAL.value

SIGNAL_POSITION_CHANGED = f"{DOMAIN}_position_changed"
SIGNAL_EVENTS_CHANGED = f"{DOMAIN}_events_changed"


STATE_ABOVE_HORIZON = "above_horizon"
STATE_BELOW_HORIZON = "below_horizon"


STATE_ATTR_AZIMUTH = "azimuth"
STATE_ATTR_ELEVATION = "elevation"
STATE_ATTR_RISING = "rising"
STATE_ATTR_NEXT_DAWN = "next_dawn"
STATE_ATTR_NEXT_DUSK = "next_dusk"
STATE_ATTR_NEXT_MIDNIGHT = "next_midnight"
STATE_ATTR_NEXT_NOON = "next_noon"
STATE_ATTR_NEXT_RISING = "next_rising"
STATE_ATTR_NEXT_SETTING = "next_setting"
