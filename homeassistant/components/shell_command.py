"""
Exposes regular shell commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/shell_command/
"""
import logging
import subprocess
import shlex

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


def setup(hass, config):
    """Setup the shell_command component."""
    conf = config.get(DOMAIN, {})

    def service_handler(call):
        """Execute a shell command service."""
        cmd = conf[call.service]
        cmd, shell = _parse_command(hass, cmd, call.data)
        if cmd is None:
            return
        try:
            subprocess.call(cmd, shell=shell,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        except subprocess.SubprocessError:
            _LOGGER.exception('Error running command: %s', cmd)

    for name in conf.keys():
        hass.services.register(DOMAIN, name, service_handler)
    return True


def _parse_command(hass, cmd, variables):
    """Parse command and fill in any template arguments if necessary."""
    cmds = cmd.split()
    prog = cmds[0]
    args = ' '.join(cmds[1:])
    try:
        rendered_args = template.render(hass, args, variables=variables)
    except TemplateError as ex:
        _LOGGER.exception('Error rendering command template: %s', ex)
        return None, None
    if rendered_args == args:
        # no template used. default behavior
        shell = True
    else:
        # template used. Must break into list and use shell=False for security
        cmd = [prog] + shlex.split(rendered_args)
        shell = False
    return cmd, shell
