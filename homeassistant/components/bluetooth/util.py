"""The bluetooth integration utilities."""
from __future__ import annotations

import platform

MAC_OS_BLUETOOTH_NAME = "corebluetooth"


async def async_get_bluetooth_adapters() -> list[str]:
    """Return a list of bluetooth adapters."""
    if platform.system() == "Windows":  # We don't have a good way to detect on windows
        return []
    if platform.system() == "Darwin":  # CoreBluetooth is built in on MacOS hardware
        return [MAC_OS_BLUETOOTH_NAME]
    from bluetooth_adapters import (  # pylint: disable=import-outside-toplevel
        get_bluetooth_adapters,
    )

    return await get_bluetooth_adapters()
