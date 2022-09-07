"""The bluetooth integration utilities."""
from __future__ import annotations

import platform

from bluetooth_auto_recovery import recover_adapter

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
    if platform.system() == "Windows":
        return {
            WINDOWS_DEFAULT_BLUETOOTH_ADAPTER: AdapterDetails(
                address=DEFAULT_ADDRESS,
                sw_version=platform.release(),
                passive_scan=False,
            )
        }
    if platform.system() == "Darwin":
        return {
            MACOS_DEFAULT_BLUETOOTH_ADAPTER: AdapterDetails(
                address=DEFAULT_ADDRESS,
                sw_version=platform.release(),
                passive_scan=False,
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
            address=adapter1["Address"],
            sw_version=adapter1["Name"],  # This is actually the BlueZ version
            hw_version=adapter1["Modalias"],
            passive_scan="org.bluez.AdvertisementMonitorManager1" in details,
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
    return adapter if address == DEFAULT_ADDRESS else f"{adapter} ({address})"


@callback
def adapter_unique_name(adapter: str, address: str) -> str:
    """Return a unique name for the adapter."""
    return adapter if address == DEFAULT_ADDRESS else address


async def async_reset_adapter(adapter: str | None) -> bool | None:
    """Reset the adapter."""
    if adapter and adapter.startswith("hci"):
        adapter_id = int(adapter[3:])
        return await recover_adapter(adapter_id)
    return False
