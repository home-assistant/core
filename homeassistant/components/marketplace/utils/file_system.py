"""File system functions."""

import asyncio
from collections.abc import Callable
import contextlib
import os
import shutil

from homeassistant.core import HomeAssistant

# From typeshed
type StrOrBytesPath = str | bytes | os.PathLike[str] | os.PathLike[bytes]
type FileDescriptorOrPath = int | StrOrBytesPath


async def async_exists(hass: HomeAssistant, path: FileDescriptorOrPath) -> bool:
    """Test whether a path exists."""
    return await hass.async_add_executor_job(os.path.exists, path)


async def async_lexists(hass: HomeAssistant, path: StrOrBytesPath) -> bool:
    """Test whether a path exists, a broken symlink counts."""
    return await hass.async_add_executor_job(os.path.lexists, path)


async def async_remove(
    hass: HomeAssistant, path: StrOrBytesPath, *, missing_ok: bool = False
) -> None:
    """Remove a path."""
    try:
        return await hass.async_add_executor_job(os.remove, path)
    except FileNotFoundError:
        if missing_ok:
            return None
        raise


async def async_remove_directory(
    hass: HomeAssistant, path: StrOrBytesPath, *, missing_ok: bool = False
) -> None:
    """Remove a directory, or the symlink to one."""
    try:
        if await hass.async_add_executor_job(os.path.islink, path):
            return await hass.async_add_executor_job(os.remove, path)
        return await hass.async_add_executor_job(shutil.rmtree, path)
    except FileNotFoundError:
        if missing_ok:
            return None
        raise


async def async_run_to_completion[T](hass: HomeAssistant, target: Callable[[], T]) -> T:
    """Run in the executor, when cancelled wait for it to finish first.

    Cancelling does not stop the thread, it would keep writing while the
    cancelled install puts the old content back.
    """
    future = hass.async_add_executor_job(target)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await future
        raise
