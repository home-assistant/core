"""The command_line component utils."""

from __future__ import annotations

import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.template import Template

from .const import DOMAIN, LOGGER

_EXEC_FAILED_CODE = 127


async def async_call_shell_with_timeout(
    command: str, timeout: int, *, log_return_code: bool = True
) -> int:
    """Run a shell command with a timeout.

    If log_return_code is set to False, it will not print an error if a non-zero
    return code is returned.
    """
    try:
        LOGGER.debug("Running command: %s", command)
        proc = await asyncio.create_subprocess_shell(  # shell by design
            command,
            close_fds=False,  # required for posix_spawn
        )
        async with asyncio.timeout(timeout):
            await proc.communicate()
    except TimeoutError:
        LOGGER.error("Timeout for command: %s", command)
        return -1

    return_code = proc.returncode
    if return_code == _EXEC_FAILED_CODE:
        LOGGER.error("Error trying to exec command: %s", command)
    elif log_return_code and return_code != 0:
        LOGGER.error(
            "Command failed (with return code %s): %s",
            proc.returncode,
            command,
        )
    return return_code or 0


async def async_check_output_or_log(command: str, timeout: int) -> str | None:
    """Run a shell command with a timeout and return the output."""
    try:
        proc = await asyncio.create_subprocess_shell(  # shell by design
            command,
            close_fds=False,  # required for posix_spawn
            stdout=asyncio.subprocess.PIPE,
        )
        async with asyncio.timeout(timeout):
            stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            LOGGER.error(
                "Command failed (with return code %s): %s", proc.returncode, command
            )
        else:
            return stdout.strip().decode("utf-8")
    except TimeoutError:
        LOGGER.error("Timeout for command: %s", command)

    return None


def render_template_args(hass: HomeAssistant, command: str) -> str | None:
    """Render template arguments for command line utilities."""
    if " " not in command:
        prog = command
        args = None
        args_compiled = None
    else:
        prog, args = command.split(" ", 1)
        args_compiled = Template(args, hass)

    rendered_args = None
    if args_compiled:
        args_to_render = {"arguments": args}
        try:
            rendered_args = args_compiled.async_render(args_to_render)
        except TemplateError as ex:
            LOGGER.exception("Error rendering command template: %s", ex)
            return None

    if rendered_args != args:
        command = f"{prog} {rendered_args}"

    LOGGER.debug("Running command: %s", command)

    return command


def create_platform_yaml_not_supported_issue(
    hass: HomeAssistant, platform_domain: str
) -> None:
    """Create an issue when platform yaml is used."""
    async_create_issue(
        hass,
        DOMAIN,
        "binary_sensor_platform_yaml_not_supported",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="platform_yaml_not_supported",
        translation_placeholders={"platform": platform_domain},
        learn_more_url="https://www.home-assistant.io/integrations/command_line/",
    )
