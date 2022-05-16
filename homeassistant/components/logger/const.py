"""Constants for the Logger integration."""

import logging

DOMAIN = "logger"

SERVICE_SET_DEFAULT_LEVEL = "set_default_level"
SERVICE_SET_LEVEL = "set_level"

LOGSEVERITY = {
    "CRITICAL": logging.CRITICAL,
    "FATAL": logging.FATAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "WARN": logging.WARN,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}

DEFAULT_LOGSEVERITY = "DEBUG"

LOGGER_DEFAULT = "default"
LOGGER_LOGS = "logs"
LOGGER_FILTERS = "filters"

ATTR_LEVEL = "level"

EVENT_LOGGING_CHANGED = "logging_changed"

STORAGE_KEY = "core.logger"
STORAGE_VERSION = 1
