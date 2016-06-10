"""
Exposes regular shell commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/shell_command/
"""
import logging
import subprocess

import voluptuous as vol

from homeassistant.helpers import template
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv

DOMAIN = 'shell_command'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

SHELL_COMMAND_SCHEMA = vol.Schema({})


def setup(hass, config):
    """Setup the shell_command component."""
    conf = config.get(DOMAIN, {})

    def service_handler(call):
        """Execute a shell command service."""
        try:
            cmd = template.render(hass, conf[call.service])
            subprocess.call(cmd, shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        except TemplateError as ex:
            _LOGGER.error('Error rendering command template: %s', ex)
        except subprocess.SubprocessError:
            _LOGGER.exception('Error running command: %s', cmd)

    for name in conf.keys():
        hass.services.register(DOMAIN, name, service_handler,
                               schema=SHELL_COMMAND_SCHEMA)
    return True
