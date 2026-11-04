"""Constants for the Debug console integration."""

from datetime import timedelta

DOMAIN = "debug_console"

# Bump when the warning changes enough that everyone has to read it again; an
# acceptance of an older version no longer counts.
WARNING_VERSION = 1
CONF_WARNING_ACCEPTED = "warning_accepted"

# How long a session outlives its last connection, so a reload or a trip to
# another page picks up where it left off.
SESSION_TIMEOUT = timedelta(minutes=30)
