"""The command_line component utils."""

import asyncio
from contextlib import suppress
from typing import Literal, overload

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity_platform import (
    async_create_platform_config_not_supported_issue,
)
from homeassistant.helpers.template import Template

from .const import DOMAIN, LOGGER

_EXEC_FAILED_CODE = 127


@overload
async def async_run_shell_command(
    command: str,
    timeout: int,
    *,
    stdin: bytes | None = ...,
    capture_stdout: Literal[False] = ...,
) -> tuple[asyncio.subprocess.Process, None]: ...


@overload
async def async_run_shell_command(
    command: str,
    timeout: int,
    *,
    stdin: bytes | None = ...,
    capture_stdout: Literal[True],
) -> tuple[asyncio.subprocess.Process, bytes]: ...


async def async_run_shell_command(
    command: str,
    timeout: int,
    *,
    stdin: bytes | None = None,
    capture_stdout: bool = False,
) -> tuple[asyncio.subprocess.Process, bytes | None]:
    """Run a shell command with a timeout and return the process and stdout.

    The returned stdout is the captured bytes when capture_stdout is set, else None.
    An OSError from spawning propagates; TimeoutError propagates after stdin cleanup
    when stdin is provided.
    """
    proc = await asyncio.create_subprocess_shell(  # shell by design
        command,
        stdin=asyncio.subprocess.PIPE if stdin is not None else None,
        stdout=asyncio.subprocess.PIPE if capture_stdout else None,
        close_fds=False,  # required for posix_spawn
    )
    try:
        async with asyncio.timeout(timeout):
            stdout, _ = await proc.communicate(input=stdin)
    except TimeoutError:
        if stdin is not None:
            with suppress(ProcessLookupError):
                # The command may have exited between the timeout and the kill.
                proc.kill()
            if (proc_stdin := proc.stdin) is not None and (
                not proc_stdin.is_closing()
                or proc_stdin.transport.get_write_buffer_size()
            ):
                # A still connected stdin pipe keeps proc.wait() pending forever,
                # see https://bugs.python.org/issue43884.
                proc_stdin.transport.abort()
            await proc.wait()
        raise
    except asyncio.CancelledError:
        # Kill synchronously so the child isn't orphaned; the event loop
        # reaps it without awaiting wait(), which cancellation would
        # interrupt anyway.
        with suppress(ProcessLookupError):
            proc.kill()
        raise
    return proc, stdout


async def async_call_shell_with_timeout(
    command: str, timeout: int, *, log_return_code: bool = True
) -> int:
    """Run a shell command with a timeout.

    If log_return_code is set to False, it will not print an error if a non-zero
    return code is returned.
    """
    LOGGER.debug("Running command: %s", command)
    try:
        proc, _ = await async_run_shell_command(command, timeout)
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
        proc, stdout = await async_run_shell_command(
            command, timeout, capture_stdout=True
        )
    except TimeoutError:
        LOGGER.error("Timeout for command: %s", command)
        return None

    if proc.returncode != 0:
        LOGGER.error(
            "Command failed (with return code %s): %s", proc.returncode, command
        )
        return None
    return stdout.strip().decode("utf-8")


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
    async_create_platform_config_not_supported_issue(
        hass,
        DOMAIN,
        platform_domain,
        yaml_config_under_integration_supported=True,
        learn_more_url="https://www.home-assistant.io/integrations/command_line/",
        logger=LOGGER,
    )
