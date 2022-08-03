"""The bluetooth integration utilities."""
from __future__ import annotations

import platform

from .const import MACOS_DEFAULT_BLUETOOTH_ADAPTER, UNIX_DEFAULT_BLUETOOTH_ADAPTER


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
    if (
        UNIX_DEFAULT_BLUETOOTH_ADAPTER in adapters
        and adapters[0] != UNIX_DEFAULT_BLUETOOTH_ADAPTER
    ):
        # The default adapter always needs to be the first in the list
        # because that is how bleak works.
        adapters.insert(0, adapters.pop(adapters.index(UNIX_DEFAULT_BLUETOOTH_ADAPTER)))
    return adapters
