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

    cache = {}

    def service_handler(call):
        """Execute a shell command service."""
        cmd = conf[call.service]

        if cmd in cache:
            prog, args, args_compiled = cache[cmd]
        elif ' ' not in cmd:
            prog = cmd
            args = None
            args_compiled = None
            cache[cmd] = prog, args, args_compiled
        else:
            prog, args = cmd.split(' ', 1)
            args_compiled = template.Template(args, hass)
            cache[cmd] = prog, args, args_compiled

        if args_compiled:
            try:
                rendered_args = args_compiled.render(call.data)
            except TemplateError as ex:
                _LOGGER.exception('Error rendering command template: %s', ex)
                return
        else:
            rendered_args = None

        if rendered_args == args:
            # no template used. default behavior
            shell = True
        else:
            # template used. Break into list and use shell=False for security
            cmd = [prog] + shlex.split(rendered_args)
            shell = False

        try:
            subprocess.call(cmd, shell=shell,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
        except subprocess.SubprocessError:
            _LOGGER.exception('Error running command: %s', cmd)

    for name in conf.keys():
        hass.services.register(DOMAIN, name, service_handler)
    return True
