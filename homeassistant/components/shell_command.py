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
        cmd, shell = _parse_command(conf[call.service], hass)
        try:
            subprocess.call(cmd, shell=shell,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        except subprocess.SubprocessError:
            _LOGGER.exception('Error running command: %s', cmd)

    for name in conf.keys():
        hass.services.register(DOMAIN, name, service_handler,
                               schema=SHELL_COMMAND_SCHEMA)
    return True


def _parse_command(cmd, hass):
    """Parse command and fill in any template arguments if necessary."""
    cmds = cmd.split()
    prog = cmds[0]
    args = ' '.join(cmds[1:])
    try:
        rendered_args = template.render(hass, args)
    except TemplateError as ex:
        _LOGGER.error('Error rendering command template: %s', ex)
    if rendered_args == args:
        # no template used. default behavior
        shell = True
    else:
        # template used. Must break into list and use shell=False for security
        cmd = [prog] + rendered_args.split()
        shell = False
    return cmd, shell
