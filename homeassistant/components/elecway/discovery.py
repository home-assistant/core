"""Find storage devices using Home Assistant's shared Zeroconf instance."""

import asyncio

from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

from homeassistant.components.zeroconf import (
    async_get_async_instance,
    info_from_service,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import SERVICE_PREFIX, SERVICE_TYPE


def storage_serial_number(name: str) -> str | None:
    """Extract identity only from the firmware's storage service name."""
    if not name.startswith(SERVICE_PREFIX) or not name.endswith(f".{SERVICE_TYPE}"):
        return None
    return name[len(SERVICE_PREFIX) : -len(f".{SERVICE_TYPE}")].strip() or None


async def async_discover(hass: HomeAssistant) -> dict[str, ZeroconfServiceInfo]:
    """Collect storage announcements without creating a second mDNS instance."""
    aiozc = await async_get_async_instance(hass)
    names: set[str] = set()

    @callback
    def service_changed(
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        if storage_serial_number(name):
            if state_change is ServiceStateChange.Removed:
                names.discard(name)
            else:
                names.add(name)

    browser = AsyncServiceBrowser(
        aiozc.zeroconf, SERVICE_TYPE, handlers=[service_changed]
    )
    try:
        await asyncio.sleep(3)
    finally:
        await browser.async_cancel()

    async def resolve(name: str) -> ZeroconfServiceInfo | None:
        info = AsyncServiceInfo(SERVICE_TYPE, name)
        if await info.async_request(aiozc.zeroconf, 2000):
            return info_from_service(info)
        return None

    discovered = await asyncio.gather(*(resolve(name) for name in sorted(names)))
    return {
        serial: info
        for info in discovered
        if info is not None and (serial := storage_serial_number(info.name))
    }
