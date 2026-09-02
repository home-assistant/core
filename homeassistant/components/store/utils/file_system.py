"""File system functions."""

from __future__ import annotations

import os
import shutil
from typing import TypeAlias

from homeassistant.core import HomeAssistant

# From typeshed
StrOrBytesPath: TypeAlias = str | bytes | os.PathLike[str] | os.PathLike[bytes]
FileDescriptorOrPath: TypeAlias = int | StrOrBytesPath


async def async_exists(hass: HomeAssistant, path: FileDescriptorOrPath) -> bool:
    """Test whether a path exists."""
    return await hass.async_add_executor_job(os.path.exists, path)


async def async_remove(
    hass: HomeAssistant, path: StrOrBytesPath, *, missing_ok: bool = False
) -> None:
    """Remove a path."""
    try:
        return await hass.async_add_executor_job(os.remove, path)
    except FileNotFoundError:
        if missing_ok:
            return
        raise


async def async_remove_directory(
    hass: HomeAssistant, path: StrOrBytesPath, *, missing_ok: bool = False
) -> None:
    """Remove a directory."""
    try:
        return await hass.async_add_executor_job(shutil.rmtree, path)
    except FileNotFoundError:
        if missing_ok:
            return
        raise
