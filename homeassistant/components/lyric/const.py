"""Constants for the Honeywell Lyric integration."""
from aiohttp.client_exceptions import ClientResponseError
from aiolyric.exceptions import LyricAuthenticationException, LyricException

DOMAIN = "lyric"

OAUTH2_AUTHORIZE = "https://api.honeywell.com/oauth2/authorize"
OAUTH2_TOKEN = "https://api.honeywell.com/oauth2/token"

PRESET_NO_HOLD = "NoHold"
PRESET_TEMPORARY_HOLD = "TemporaryHold"
PRESET_HOLD_UNTIL = "HoldUntil"
PRESET_PERMANENT_HOLD = "PermanentHold"
PRESET_VACATION_HOLD = "VacationHold"

LYRIC_EXCEPTIONS = (
    LyricAuthenticationException,
    LyricException,
    ClientResponseError,
)
