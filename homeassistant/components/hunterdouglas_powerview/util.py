"""Coordinate data for powerview devices."""

from __future__ import annotations

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.hub import Hub

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .model import PowerviewAPI, PowerviewDeviceInfo


async def async_connect_hub(
    hass: HomeAssistant, address: str, api_version: int | None = None
) -> PowerviewAPI:
    """Create the hub and fetch the device info address."""
    websession = async_get_clientsession(hass)
    pv_request = AioRequest(
        address, loop=hass.loop, websession=websession, api_version=api_version
    )
    hub = Hub(pv_request)
    await hub.query_firmware()
    info = PowerviewDeviceInfo(
        name=hub.name,
        mac_address=hub.mac_address,
        serial_number=hub.serial_number,
        firmware=hub.firmware,
        model=hub.model,
        hub_address=hub.ip,
    )
    return PowerviewAPI(hub, pv_request, info)
