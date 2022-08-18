"""The bluetooth integration utilities."""
from __future__ import annotations

import platform

from homeassistant.core import callback

from .const import (
    DEFAULT_ADAPTER_BY_PLATFORM,
    DEFAULT_ADDRESS,
    MACOS_DEFAULT_BLUETOOTH_ADAPTER,
    UNIX_DEFAULT_BLUETOOTH_ADAPTER,
    WINDOWS_DEFAULT_BLUETOOTH_ADAPTER,
    AdapterDetails,
)


async def async_get_bluetooth_adapters() -> dict[str, AdapterDetails]:
    """Return a list of bluetooth adapters."""
    if platform.system() == "Windows":  # We don't have a good way to detect on windows
        return {
            WINDOWS_DEFAULT_BLUETOOTH_ADAPTER: AdapterDetails(
                name=WINDOWS_DEFAULT_BLUETOOTH_ADAPTER,
                address=DEFAULT_ADDRESS,
            )
        }
    if platform.system() == "Darwin":  # CoreBluetooth is built in on MacOS hardware
        return {
            MACOS_DEFAULT_BLUETOOTH_ADAPTER: AdapterDetails(
                name=MACOS_DEFAULT_BLUETOOTH_ADAPTER,
                address=DEFAULT_ADDRESS,
            )
        }
    from bluetooth_adapters import (  # pylint: disable=import-outside-toplevel
        get_bluetooth_adapter_details,
    )

    adapters: dict[str, AdapterDetails] = {}
    adapter_details = await get_bluetooth_adapter_details()
    for adapter, details in adapter_details.items():
        adapter1 = details["org.bluez.Adapter1"]
        adapters[adapter] = AdapterDetails(
            name=adapter1["Address"],
            address=adapter1["Address"],  # This is the best name we have
            sw_version=adapter1["Name"],
            hw_version=adapter1["Modalias"],
            powered=adapter1["Powered"],
            discovering=adapter1["Discovering"],
        )
    return adapters


@callback
def async_default_adapter() -> str:
    """Return the default adapter for the platform."""
    return DEFAULT_ADAPTER_BY_PLATFORM.get(
        platform.system(), UNIX_DEFAULT_BLUETOOTH_ADAPTER
    )


@callback
def adapter_human_name(adapter: str, address: str) -> str:
    """Return a human readable name for the adapter."""
    return adapter if address == DEFAULT_ADDRESS else f"{address} ({adapter})"
