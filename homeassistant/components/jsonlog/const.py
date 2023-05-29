"""Constants for the jsonlog integration."""
import logging
from typing import Final

from homeassistant.backports.enum import StrEnum

DOMAIN: Final = "jsonlog"
LOGGER = logging.getLogger(__package__)


class LogAttribute(StrEnum):
    """Supported log record attributes."""

    ASCTIME = "asctime"
    CREATED = "created"
    FILENAME = "filename"
    FUNCNAME = "funcName"
    LEVELNAME = "levelname"
    LEVELNO = "levelno"
    LINENO = "lineno"
    MESSAGE = "message"
    MODULE = "module"
    MSECS = "msecs"
    NAME = "name"
    PATHNAME = "pathname"
    PROCESSNAME = "processName"
    PROCESS = "process"
    RELATIVECREATED = "relativeCreated"
    THREADNAME = "threadName"
    THREAD = "thread"


LOGATTRS = [f.value for f in LogAttribute]

DEFAULT_FILENAME = DOMAIN + ".log"

CONF_ATTRIBUTES = "attributes"

SERVICE_ROTATE = "rotate"
