"""Constants for the Logger integration."""

from enum import StrEnum
import logging

DOMAIN = "logger"

SERVICE_SET_LEVEL = "set_level"

LOGSEVERITY_NOTSET = "NOTSET"
LOGSEVERITY_DEBUG = "DEBUG"
LOGSEVERITY_INFO = "INFO"
LOGSEVERITY_WARNING = "WARNING"
LOGSEVERITY_ERROR = "ERROR"
LOGSEVERITY_CRITICAL = "CRITICAL"
LOGSEVERITY_WARN = "WARN"
LOGSEVERITY_FATAL = "FATAL"

LOGSEVERITY = {
    LOGSEVERITY_CRITICAL: logging.CRITICAL,
    LOGSEVERITY_FATAL: logging.FATAL,
    LOGSEVERITY_ERROR: logging.ERROR,
    LOGSEVERITY_WARNING: logging.WARNING,
    LOGSEVERITY_WARN: logging.WARNING,
    LOGSEVERITY_INFO: logging.INFO,
    LOGSEVERITY_DEBUG: logging.DEBUG,
    LOGSEVERITY_NOTSET: logging.NOTSET,
}


DEFAULT_LOGSEVERITY = "DEBUG"

LOGGER_DEFAULT = "default"
LOGGER_LOGS = "logs"
LOGGER_FILTERS = "filters"

STORAGE_KEY = "core.logger"
STORAGE_LOG_KEY = "logs"
STORAGE_VERSION = 1


class LoggerService(StrEnum):
    """Store keys for logger services."""

    SET_DEFAULT_LEVEL = "set_default_level"
    SET_LEVEL = "set_level"


class LoggerServiceArgument(StrEnum):
    """Store keys for logger service arguments."""

    LEVEL = "level"
