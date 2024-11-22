"""Coordinate data for powerview devices."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from aiopvapi.helpers.aiorequest import AioRequest
from aiopvapi.helpers.constants import ATTR_ID
from aiopvapi.hub import Hub

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .model import PowerviewAPI, PowerviewDeviceInfo


@callback
def async_map_data_by_id(data: Iterable[dict[str | int, Any]]):
    """Return a dict with the key being the id for a list of entries."""
    return {entry[ATTR_ID]: entry for entry in data}


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
