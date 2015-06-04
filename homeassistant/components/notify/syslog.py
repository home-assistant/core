"""
homeassistant.components.notify.syslog
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Syslog notification service.

Configuration:

To use the Syslog notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: syslog
  facility: SYSLOG_FACILITY
  option: SYSLOG_LOG_OPTION
  priority: SYSLOG_PRIORITY

Variables:

facility
*Optional
Facility according to RFC 3164 (http://tools.ietf.org/html/rfc3164). Default
is 'syslog' if no value is given.

option
*Option
Log option. Default is 'pid' if no value is given.

priority
*Optional
Priority of the messages. Default is 'info' if no value is given.
"""
import logging
import syslog

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)
FACILITIES = {'kernel': syslog.LOG_KERN,
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
              'local7': syslog.LOG_LOCAL7}

OPTIONS = {'pid': syslog.LOG_PID,
           'cons': syslog.LOG_CONS,
           'ndelay': syslog.LOG_NDELAY,
           'nowait': syslog.LOG_NOWAIT,
           'perror': syslog.LOG_PERROR}

PRIORITIES = {5: syslog.LOG_EMERG,
              4: syslog.LOG_ALERT,
              3: syslog.LOG_CRIT,
              2: syslog.LOG_ERR,
              1: syslog.LOG_WARNING,
              0: syslog.LOG_NOTICE,
              -1: syslog.LOG_INFO,
              -2: syslog.LOG_DEBUG}


def get_service(hass, config):
    """ Get the mail notification service. """

    if not validate_config(config,
                           {DOMAIN: ['facility',
                                     'option',
                                     'priority']},
                           _LOGGER):
        return None

    _facility = FACILITIES.get(config[DOMAIN]['facility'], 40)
    _option = OPTIONS.get(config[DOMAIN]['option'], 10)
    _priority = PRIORITIES.get(config[DOMAIN]['priority'], -1)

    return SyslogNotificationService(_facility, _option, _priority)


# pylint: disable=too-few-public-methods
class SyslogNotificationService(BaseNotificationService):
    """ Implements syslog notification service. """

    # pylint: disable=too-many-arguments
    def __init__(self, facility, option, priority):
        self._facility = facility
        self._option = option
        self._priority = priority

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        syslog.openlog(title, self._option, self._facility)
        syslog.syslog(self._priority, message)
        syslog.closelog()
