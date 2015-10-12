"""
homeassistant.components.shell_command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Component to expose shell commands as services.

shell_command:
  restart_pow: touch ~/.pow/restart.txt

"""
import logging
import subprocess

from homeassistant.util import slugify

DOMAIN = 'shell_command'
DEPENDENCIES = []

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Sets up the shell_command component. """
    conf = config.get(DOMAIN)

    if not isinstance(conf, dict):
        _LOGGER.error('Expected configuration to be a dictionary')
        return False

    for name in conf.keys():
        if name != slugify(name):
            _LOGGER.error('Invalid service name: %s. Try %s',
                          name, slugify(name))
            return False

    def service_handler(call):
        """ Execute a shell command service. """
        try:
            subprocess.call(conf[call.service].split(' '),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        except subprocess.SubprocessError:
            _LOGGER.exception('Error running command')

    for name in conf.keys():
        hass.services.register(DOMAIN, name, service_handler)

    return True
