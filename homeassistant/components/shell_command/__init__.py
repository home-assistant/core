"""Expose regular shell commands as services."""
import asyncio
import logging
import shlex

import voluptuous as vol

from homeassistant.exceptions import TemplateError
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

DOMAIN = 'shell_command'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.schema_with_slug_keys(cv.string),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the shell_command component."""
    conf = config.get(DOMAIN, {})

    cache = {}

    async def async_service_handler(service: ServiceCall) -> None:
        """Execute a shell command service."""
        cmd = conf[service.service]

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
                rendered_args = args_compiled.async_render(service.data)
            except TemplateError as ex:
                _LOGGER.exception("Error rendering command template: %s", ex)
                return
        else:
            rendered_args = None

        if rendered_args == args:
            # No template used. default behavior

            # pylint: disable=no-member
            create_process = asyncio.subprocess.create_subprocess_shell(
                cmd,
                loop=hass.loop,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                )
        else:
            # Template used. Break into list and use create_subprocess_exec
            # (which uses shell=False) for security
            shlexed_cmd = [prog] + shlex.split(rendered_args)

            # pylint: disable=no-member
            create_process = asyncio.subprocess.create_subprocess_exec(
                *shlexed_cmd,
                loop=hass.loop,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                )

        process = await create_process
        stdout_data, stderr_data = await process.communicate()

        if stdout_data:
            _LOGGER.debug("Stdout of command: `%s`, return code: %s:\n%s",
                          cmd, process.returncode, stdout_data)
        if stderr_data:
            _LOGGER.debug("Stderr of command: `%s`, return code: %s:\n%s",
                          cmd, process.returncode, stderr_data)
        if process.returncode != 0:
            _LOGGER.exception("Error running command: `%s`, return code: %s",
                              cmd, process.returncode)

    for name in conf.keys():
        hass.services.async_register(DOMAIN, name, async_service_handler)
    return True
