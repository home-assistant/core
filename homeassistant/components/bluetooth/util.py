"""The bluetooth integration utilities."""
from __future__ import annotations

import platform

from .const import LINUX_DEFAULT_BLUETOOTH_ADAPTER, MACOS_DEFAULT_BLUETOOTH_ADAPTER


async def async_get_bluetooth_adapters() -> list[str]:
    """Return a list of bluetooth adapters."""
    if platform.system() == "Windows":  # We don't have a good way to detect on windows
        return []
    if platform.system() == "Darwin":  # CoreBluetooth is built in on MacOS hardware
        return [MACOS_DEFAULT_BLUETOOTH_ADAPTER]
    from bluetooth_adapters import (  # pylint: disable=import-outside-toplevel
        get_bluetooth_adapters,
    )

    adapters = await get_bluetooth_adapters()
    if LINUX_DEFAULT_BLUETOOTH_ADAPTER in adapters:
        # The default adapter always needs to be the first in the list
        # because that is how bleak works.
        adapters.remove(LINUX_DEFAULT_BLUETOOTH_ADAPTER)
        return [LINUX_DEFAULT_BLUETOOTH_ADAPTER, *adapters]
    return adapters
