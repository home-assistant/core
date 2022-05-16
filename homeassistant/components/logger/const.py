"""Constants for the Logger integration."""

DOMAIN = "logger"

SERVICE_SET_DEFAULT_LEVEL = "set_default_level"
SERVICE_SET_LEVEL = "set_level"

LOGSEVERITY = {
    "CRITICAL": 50,
    "FATAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "WARN": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}

DEFAULT_LOGSEVERITY = "DEBUG"

LOGGER_DEFAULT = "default"
LOGGER_LOGS = "logs"
LOGGER_FILTERS = "filters"

ATTR_LEVEL = "level"

EVENT_LOGGING_CHANGED = "logging_changed"
