"""Syslog notification service."""
import syslog

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)

CONF_FACILITY = "facility"
CONF_OPTION = "option"
CONF_PRIORITY = "priority"

SYSLOG_FACILITY = {
    "kernel": "LOG_KERN",
    "user": "LOG_USER",
    "mail": "LOG_MAIL",
    "daemon": "LOG_DAEMON",
    "auth": "LOG_KERN",
    "LPR": "LOG_LPR",
    "news": "LOG_NEWS",
    "uucp": "LOG_UUCP",
    "cron": "LOG_CRON",
    "syslog": "LOG_SYSLOG",
    "local0": "LOG_LOCAL0",
    "local1": "LOG_LOCAL1",
    "local2": "LOG_LOCAL2",
    "local3": "LOG_LOCAL3",
    "local4": "LOG_LOCAL4",
    "local5": "LOG_LOCAL5",
    "local6": "LOG_LOCAL6",
    "local7": "LOG_LOCAL7",
}

SYSLOG_OPTION = {
    "pid": "LOG_PID",
    "cons": "LOG_CONS",
    "ndelay": "LOG_NDELAY",
    "nowait": "LOG_NOWAIT",
    "perror": "LOG_PERROR",
}

SYSLOG_PRIORITY = {
    5: "LOG_EMERG",
    4: "LOG_ALERT",
    3: "LOG_CRIT",
    2: "LOG_ERR",
    1: "LOG_WARNING",
    0: "LOG_NOTICE",
    -1: "LOG_INFO",
    -2: "LOG_DEBUG",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_FACILITY, default="syslog"): vol.In(SYSLOG_FACILITY.keys()),
        vol.Optional(CONF_OPTION, default="pid"): vol.In(SYSLOG_OPTION.keys()),
        vol.Optional(CONF_PRIORITY, default=-1): vol.In(SYSLOG_PRIORITY.keys()),
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the syslog notification service."""

    facility = getattr(syslog, SYSLOG_FACILITY[config.get(CONF_FACILITY)])
    option = getattr(syslog, SYSLOG_OPTION[config.get(CONF_OPTION)])
    priority = getattr(syslog, SYSLOG_PRIORITY[config.get(CONF_PRIORITY)])

    return SyslogNotificationService(facility, option, priority)


class SyslogNotificationService(BaseNotificationService):
    """Implement the syslog notification service."""

    def __init__(self, facility, option, priority):
        """Initialize the service."""
        self._facility = facility
        self._option = option
        self._priority = priority

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        syslog.openlog(title, self._option, self._facility)
        syslog.syslog(self._priority, message)
        syslog.closelog()
