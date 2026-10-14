"""Constants for the Debug console integration."""

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import __version__
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .session import ConsoleSession

DOMAIN = "debug_console"

# Both development and nightly builds have a ".dev" version.
IS_DEVELOPMENT_VERSION = ".dev" in __version__

# Bump when the warning changes enough that everyone has to read it again; an
# acceptance of an older version no longer counts.
WARNING_VERSION = 1
CONF_WARNING_ACCEPTED = "warning_accepted"

# Sessions per user ID and session ID.
DATA_CONSOLE_SESSIONS: HassKey[dict[tuple[str, str], ConsoleSession]] = HassKey(
    "debug_console_sessions"
)

# How long a session outlives its last connection, so a reload or a trip to
# another page picks up where it left off.
SESSION_TIMEOUT = timedelta(minutes=30)
