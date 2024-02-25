"""The Matter integration."""
from __future__ import annotations

from functools import cache
import importlib
import sys

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .helpers import MatterDeviceInfo, node_from_ha_device_id

CONNECT_TIMEOUT = 10
LISTEN_READY_TIMEOUT = 30


@callback
@cache
def get_matter_device_info(
    hass: HomeAssistant, device_id: str
) -> MatterDeviceInfo | None:
    """Return Matter device info or None if device does not exist."""
    if not (node := node_from_ha_device_id(hass, device_id)):
        return None

    return MatterDeviceInfo(
        unique_id=node.device_info.uniqueID,
        vendor_id=hex(node.device_info.vendorID),
        product_id=hex(node.device_info.productID),
    )


async def _async_load_core(hass: HomeAssistant) -> None:
    """Load the core component.

    This function is used to avoid loading chip and matter_server
    from the event loop.
    """
    if "matter_server" not in sys.modules:
        await hass.async_add_executor_job(importlib.import_module, "matter_server")
    # pylint:disable-next=import-outside-toplevel
    from .core import async_remove_entry, async_setup_entry, async_unload_entry

    _module = sys.modules[__name__]
    setattr(_module, "async_setup_entry", async_setup_entry)
    setattr(_module, "async_unload_entry", async_unload_entry)
    setattr(_module, "async_remove_entry", async_remove_entry)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Matter integration."""
    await _async_load_core(hass)
    return True
