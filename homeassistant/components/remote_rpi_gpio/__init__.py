"""Support for controlling GPIO pins of a Raspberry Pi."""
import logging

_LOGGER = logging.getLogger(__name__)

CONF_BOUNCETIME = "bouncetime"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PULL_MODE = "pull_mode"

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = "UP"

# The domain of your component. Should be equal to the name of your component.
DOMAIN = "remote_rpi_gpio"

# List of integration names (string) your integration depends upon.
DEPENDENCIES = []


def setup(hass, config):
    """Set up remote_rpi_gpio."""
    _LOGGER.info("loading %s completed.", DOMAIN)
    return True
