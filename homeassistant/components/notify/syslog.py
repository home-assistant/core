"""
Syslog notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.syslog/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the syslog notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['facility', 'option', 'priority']},
                           _LOGGER):
        return None

    import syslog

    _facility = {
        'kernel': syslog.LOG_KERN,
        'user': syslog.LOG_USER,
        'mail': syslog.LOG_MAIL,
        'daemon': syslog.LOG_DAEMON,
        'auth': syslog.LOG_KERN,
        'LPR': syslog.LOG_LPR,
        'news': syslog.LOG_NEWS,
        'uucp': syslog.LOG_UUCP,
        'cron': syslog.LOG_CRON,
        'syslog': syslog.LOG_SYSLOG,
        'local0': syslog.LOG_LOCAL0,
        'local1': syslog.LOG_LOCAL1,
        'local2': syslog.LOG_LOCAL2,
        'local3': syslog.LOG_LOCAL3,
        'local4': syslog.LOG_LOCAL4,
        'local5': syslog.LOG_LOCAL5,
        'local6': syslog.LOG_LOCAL6,
        'local7': syslog.LOG_LOCAL7,
    }.get(config['facility'], 40)

    _option = {
        'pid': syslog.LOG_PID,
        'cons': syslog.LOG_CONS,
        'ndelay': syslog.LOG_NDELAY,
        'nowait': syslog.LOG_NOWAIT,
        'perror': syslog.LOG_PERROR
    }.get(config['option'], 10)

    _priority = {
        5: syslog.LOG_EMERG,
        4: syslog.LOG_ALERT,
        3: syslog.LOG_CRIT,
        2: syslog.LOG_ERR,
        1: syslog.LOG_WARNING,
        0: syslog.LOG_NOTICE,
        -1: syslog.LOG_INFO,
        -2: syslog.LOG_DEBUG
    }.get(config['priority'], -1)

    return SyslogNotificationService(_facility, _option, _priority)


# pylint: disable=too-few-public-methods
class SyslogNotificationService(BaseNotificationService):
    """Implement the syslog notification service."""

    # pylint: disable=too-many-arguments
    def __init__(self, facility, option, priority):
        """Initialize the service."""
        self._facility = facility
        self._option = option
        self._priority = priority

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        import syslog

        title = kwargs.get(ATTR_TITLE)

        syslog.openlog(title, self._option, self._facility)
        syslog.syslog(self._priority, message)
        syslog.closelog()
