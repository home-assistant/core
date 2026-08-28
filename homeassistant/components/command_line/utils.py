"""The command_line component utils."""

import asyncio
from contextlib import suppress
import hashlib
import shlex
from typing import Literal, overload

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import (
    async_create_platform_config_not_supported_issue,
)
from homeassistant.helpers.template import Template
from homeassistant.util import slugify

from .const import DOMAIN, LOGGER

_EXEC_FAILED_CODE = 127
# Characters that make a rendered command behave differently under /bin/sh than
# under exec. Kept only until the shell path is removed in 2027.4. "!" is
# excluded: pipeline negation only applies at a command-word start, and rendered
# args never sit in that position, so it is always literal here across dash,
# BusyBox ash and bash. "{" and "}" are kept because bash used as /bin/sh does
# brace expansion (dash/ash do not). "~" and "#" are kept because they are
# position-dependent (tilde expands at a word start, "#" starts a comment) and a
# flat membership test cannot check position, so we over-warn to stay safe.
_SHELL_FEATURE_CHARS = frozenset("|&;<>()$`*?[]{}~#\n")
_DEPRECATION_ISSUE_BREAKS_IN = "2027.4.0"
_LEARN_MORE_URL = "https://www.home-assistant.io/integrations/command_line/"


def _has_shell_features(rendered_args: str) -> bool:
    """Return True if rendered_args contains shell metacharacters."""
    return any(c in _SHELL_FEATURE_CHARS for c in rendered_args)


@callback
def _update_issue(
    hass: HomeAssistant,
    issue_id: str,
    prog: str,
    platform: str,
    name: str,
    *,
    create: bool,
) -> None:
    """Create or delete a repair issue."""
    if not create:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=_DEPRECATION_ISSUE_BREAKS_IN,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="shell_command_template_deprecation",
        translation_placeholders={
            "program": prog,
            "platform": platform,
            "name": name,
        },
        learn_more_url=_LEARN_MORE_URL,
    )


@overload
async def async_run_shell_command(
    command: str | list[str],
    timeout: int,
    *,
    stdin: bytes | None = ...,
    capture_stdout: Literal[False] = ...,
) -> tuple[asyncio.subprocess.Process, None]: ...


@overload
async def async_run_shell_command(
    command: str | list[str],
    timeout: int,
    *,
    stdin: bytes | None = ...,
    capture_stdout: Literal[True],
) -> tuple[asyncio.subprocess.Process, bytes]: ...


async def async_run_shell_command(
    command: str | list[str],
    timeout: int,
    *,
    stdin: bytes | None = None,
    capture_stdout: bool = False,
) -> tuple[asyncio.subprocess.Process, bytes | None]:
    """Run a command with a timeout and return the process and stdout.

    A list command is run via exec (shell=False); a str command via the shell.
    The returned stdout is the captured bytes when capture_stdout is set, else None.
    An OSError from spawning propagates; TimeoutError propagates after stdin cleanup
    when stdin is provided.
    """
    stdin_pipe = asyncio.subprocess.PIPE if stdin is not None else None
    stdout_pipe = asyncio.subprocess.PIPE if capture_stdout else None
    if isinstance(command, list):
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=stdin_pipe,
            stdout=stdout_pipe,
            close_fds=False,  # required for posix_spawn
        )
    else:
        proc = await asyncio.create_subprocess_shell(  # shell by design
            command,
            stdin=stdin_pipe,
            stdout=stdout_pipe,
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
    command: str | list[str], timeout: int, *, log_return_code: bool = True
) -> int:
    """Run a command with a timeout.

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


async def async_check_output_or_log(
    command: str | list[str], timeout: int
) -> str | None:
    """Run a command with a timeout and return the output."""
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


@callback
def render_template_args(
    hass: HomeAssistant, command: str, platform: str, name: str
) -> str | list[str] | None:
    """Render template arguments for command line utilities."""
    if " " not in command:
        LOGGER.debug("Running command: %s", command)
        return command

    prog, args = command.split(" ", 1)
    args_compiled = Template(args, hass)

    try:
        # parse_result=False keeps the output a string; the args are executed as a
        # command, so parsing them into Python literals would corrupt values such
        # as "1_000" (-> 1000) or "1e3" (-> 1000.0).
        rendered_args = args_compiled.async_render(
            {"arguments": args}, parse_result=False
        )
    except TemplateError as ex:
        LOGGER.exception("Error rendering command template: %s", ex)
        return None

    if rendered_args == args:
        # No template substitution — keep shell path.
        LOGGER.debug("Running command: %s", command)
        return command

    # Template substitution occurred. Determine the safe execution path.
    # The name is part of the issue id so two entities that happen to share a
    # command string get their own issue instead of collapsing into one.
    command_hash = hashlib.sha256(command.encode()).hexdigest()[:8]
    issue_id = f"shell_command_template_{platform}_{slugify(name)}_{command_hash}"

    if _has_shell_features(rendered_args):
        # Shell features (pipes, redirects, etc.) detected in the rendered args.
        # During the deprecation period, keep the shell path and notify the user.
        _update_issue(hass, issue_id, prog, platform, name, create=True)
        assembled = f"{prog} {rendered_args}"
        LOGGER.debug("Running command: %s", assembled)
        return assembled

    # No shell features — use exec (shell=False) for security.
    _update_issue(hass, issue_id, prog, platform, name, create=False)
    try:
        split_args = shlex.split(rendered_args)
    except ValueError as ex:
        # E.g. an unbalanced quote in the rendered value (like an apostrophe).
        LOGGER.error("Error parsing command arguments %s: %s", rendered_args, ex)
        return None
    exec_cmd = [prog, *split_args]
    LOGGER.debug("Running command: %s", shlex.join(exec_cmd))
    return exec_cmd


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
