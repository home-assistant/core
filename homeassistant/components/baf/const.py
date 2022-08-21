"""Constants for the Big Ass Fans integration."""

DOMAIN = "baf"

# Most properties are pushed, only the
# query every 5 minutes so we keep the RPM
# sensors up to date
QUERY_INTERVAL = 300

RUN_TIMEOUT = 20

PRESET_MODE_AUTO = "Auto"

SPEED_COUNT = 7
SPEED_RANGE = (1, SPEED_COUNT)

ONE_MIN_SECS = 60
ONE_DAY_SECS = 86400
HALF_DAY_SECS = 43200
