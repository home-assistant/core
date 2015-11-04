"""
homeassistant.components.logger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component that will help guide the user taking its first steps.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/logger.html

Sample configuration

logger:
  default: critical
  logs:
    homeassistant.components: debug
    homeassistant.components.device_tracker: critical
    homeassistant.components.camera: critical

"""
import logging

DOMAIN = 'logger'
DEPENDENCIES = []

LOGSEVERITY = {
    'CRITICAL': 50,
    'FATAL': 50,
    'ERROR': 40,
    'WARNING': 30,
    'WARN': 30,
    'INFO': 20,
    'DEBUG': 10,
    'NOTSET': 0
}

LOGGER_DEFAULT = 'default'
LOGGER_LOGS = 'logs'


class HomeAssistantLogFilter(logging.Filter):
    """A Home Assistant log filter"""
    # pylint: disable=no-init,too-few-public-methods

    def __init__(self, logfilter):
        super().__init__()

        self.logfilter = logfilter

    def filter(self, record):

        # Log with filterd severity
        if LOGGER_LOGS in self.logfilter:
            for keyvalue in self.logfilter[LOGGER_LOGS]:
                filtername = keyvalue[0]
                logseverity = keyvalue[1]
                if record.name.startswith(filtername):
                    return record.levelno >= logseverity

        # Log with default severity
        default = self.logfilter[LOGGER_DEFAULT]
        return record.levelno >= default


def setup(hass, config=None):
    """ Setup the logger component. """

    root_logger = logging.getLogger()

    loggerconfig = config.get(DOMAIN)
    logfilter = dict()

    # Set default log severity
    logfilter[LOGGER_DEFAULT] = LOGSEVERITY['debug'.upper()]
    if LOGGER_DEFAULT in loggerconfig:
        logfilter[LOGGER_DEFAULT] = LOGSEVERITY[
            loggerconfig[LOGGER_DEFAULT].upper()
        ]

    # Compute logseverity for components
    if LOGGER_LOGS in loggerconfig:
        for key, value in loggerconfig[LOGGER_LOGS].items():
            loggerconfig[LOGGER_LOGS][key] = LOGSEVERITY[value.upper()]

        logs = sorted(
            loggerconfig[LOGGER_LOGS].items(),
            key=lambda t: t[0],
            reverse=True
        )
        logfilter[LOGGER_LOGS] = logs

    # Set log filter for all log handler
    for handler in logging.root.handlers:
        handler.addFilter(HomeAssistantLogFilter(logfilter))
        root_logger.info(logfilter)

    return True
