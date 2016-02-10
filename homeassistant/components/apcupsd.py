"""
homeassistant.components.apcupsd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sets up and provides access to the status output of APCUPSd via its Network
Information Server (NIS).
"""
import logging


DOMAIN = "apcupsd"
REQUIREMENTS = ("apcaccess==0.0.4",)

CONF_HOST = "host"
CONF_PORT = "port"
CONF_TYPE = "type"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3551

KEY_STATUS = "STATUS"

VALUE_ONLINE = "ONLINE"

GET_STATUS = None

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Use config values to set up a function enabling status retrieval. """
    global GET_STATUS
    from apcaccess import status

    host = config[DOMAIN].get(CONF_HOST, DEFAULT_HOST)
    port = config[DOMAIN].get(CONF_PORT, DEFAULT_PORT)

    def get_status():
        """ Get the status from APCUPSd and parse it into a dict. """
        return status.parse(status.get(host=host, port=port))

    GET_STATUS = get_status

    # It doesn't really matter why we're not able to get the status, just that
    # we can't.
    # pylint: disable=broad-except
    try:
        GET_STATUS()
    except Exception:
        _LOGGER.exception("Failure while testing APCUPSd status retrieval.")
        return False
    return True
