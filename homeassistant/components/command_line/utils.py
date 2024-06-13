"""The command_line component utils."""

from __future__ import annotations

import asyncio
import logging

_LOGGER = logging.getLogger(__name__)
_EXEC_FAILED_CODE = 127


async def async_call_shell_with_timeout(
    command: str, timeout: int, *, log_return_code: bool = True
) -> int:
    """Run a shell command with a timeout.

    If log_return_code is set to False, it will not print an error if a non-zero
    return code is returned.
    """
    try:
        _LOGGER.debug("Running command: %s", command)
        proc = await asyncio.create_subprocess_shell(  # shell by design
            command,
            close_fds=False,  # required for posix_spawn
        )
        async with asyncio.timeout(timeout):
            await proc.communicate()
    except TimeoutError:
        _LOGGER.error("Timeout for command: %s", command)
        return -1

    return_code = proc.returncode
    if return_code == _EXEC_FAILED_CODE:
        _LOGGER.error("Error trying to exec command: %s", command)
    elif log_return_code and return_code != 0:
        _LOGGER.error(
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
            _LOGGER.error(
                "Command failed (with return code %s): %s", proc.returncode, command
            )
        else:
            return stdout.strip().decode("utf-8")
    except TimeoutError:
        _LOGGER.error("Timeout for command: %s", command)

    return None
