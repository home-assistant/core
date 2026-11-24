"""Constants for the system log integration."""

CONF_MAX_ENTRIES = "max_entries"
CONF_FIRE_EVENT = "fire_event"

DATA_SYSTEM_LOG = "system_log"
DEFAULT_MAX_ENTRIES = 50
DEFAULT_FIRE_EVENT = False
DOMAIN = "system_log"

EVENT_SYSTEM_LOG = "system_log_event"

RAW_BACKLOG_LINES = 100
RAW_INTEGRATION_BACKLOG_LINES = 5000
# A log file is searched whole for the lines of an integration, a log reader
# only this far back
RAW_INTEGRATION_READER_LINES = 50_000
RAW_BUFFER_LINES = 1000
RAW_UPDATE_COOLDOWN = 0.5
