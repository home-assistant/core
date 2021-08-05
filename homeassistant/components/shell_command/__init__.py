"""Expose regular shell commands as services."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import shlex

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.typing import ConfigType

DOMAIN = "shell_command"

COMMAND_TIMEOUT = 60

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(cv.string)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the shell_command component."""
    conf = config.get(DOMAIN, {})

    cache: dict[str, tuple[str, str | None, template.Template | None]] = {}

    async def async_service_handler(service: ServiceCall) -> None:
        """Execute a shell command service."""
        cmd = conf[service.service]

        if cmd in cache:
            prog, args, args_compiled = cache[cmd]
        elif " " not in cmd:
            prog = cmd
            args = None
            args_compiled = None
            cache[cmd] = prog, args, args_compiled
        else:
            prog, args = cmd.split(" ", 1)
            args_compiled = template.Template(args, hass)
            cache[cmd] = prog, args, args_compiled

        if args_compiled:
            try:
                rendered_args = args_compiled.async_render(
                    variables=service.data, parse_result=False
                )
            except TemplateError as ex:
                _LOGGER.exception("Error rendering command template: %s", ex)
                return
        else:
            rendered_args = None

        if rendered_args == args:
            # No template used. default behavior

            create_process = asyncio.create_subprocess_shell(
                cmd,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            # Template used. Break into list and use create_subprocess_exec
            # (which uses shell=False) for security
            shlexed_cmd = [prog] + shlex.split(rendered_args)

            create_process = asyncio.create_subprocess_exec(
                *shlexed_cmd,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        process = await create_process
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(), COMMAND_TIMEOUT
            )
        except asyncio.TimeoutError:
            _LOGGER.exception(
                "Timed out running command: `%s`, after: %ss", cmd, COMMAND_TIMEOUT
            )
            if process:
                with suppress(TypeError):
                    process.kill()
                    # https://bugs.python.org/issue43884
                    # pylint: disable=protected-access
                    process._transport.close()  # type: ignore[attr-defined]
                del process

            return

        if stdout_data:
            _LOGGER.debug(
                "Stdout of command: `%s`, return code: %s:\n%s",
                cmd,
                process.returncode,
                stdout_data,
            )
        if stderr_data:
            _LOGGER.debug(
                "Stderr of command: `%s`, return code: %s:\n%s",
                cmd,
                process.returncode,
                stderr_data,
            )
        if process.returncode != 0:
            _LOGGER.exception(
                "Error running command: `%s`, return code: %s", cmd, process.returncode
            )

    for name in conf:
        hass.services.async_register(DOMAIN, name, async_service_handler)
    return True
