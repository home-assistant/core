"""
homeassistant.components.tcp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A generic TCP socket component.
"""
DOMAIN = "tcp"

CONF_PORT = "port"
CONF_TIMEOUT = "timeout"
CONF_PAYLOAD = "payload"
CONF_UNIT = "unit"
CONF_VALUE_REGEX = "value_regex"
CONF_VALUE_ON = "value_on"
CONF_BUFFER_SIZE = "buffer_size"

DEFAULT_TIMEOUT = 10
DEFAULT_BUFFER_SIZE = 1024


def setup(hass, config):
    """ Nothing to do! """
    return True
