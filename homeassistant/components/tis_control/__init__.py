"""The TISControl integration."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import aiofiles
from aiohttp import web
from attr import dataclass
from TISControlProtocol.api import TISApi
from TISControlProtocol.Protocols.udp.ProtocolHandler import (
    TISPacket,
    TISProtocolHandler,
)

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DEVICES_DICT, DOMAIN

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SENSOR, Platform.SWITCH]
type TISConfigEntry = ConfigEntry[TISData]
protocol_handler = TISProtocolHandler()


@dataclass
class TISData:
    """TISControl data stored in the ConfigEntry."""

    api: TISApi


async def async_setup_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Set up TISControl from a config entry."""
    tis_api = TISApi(
        port=int(entry.data["port"]),
        hass=hass,
        domain=DOMAIN,
        devices_dict=DEVICES_DICT,
    )
    entry.runtime_data = TISData(api=tis_api)

    hass.data.setdefault(DOMAIN, {"supported_platforms": PLATFORMS})
    try:
        await tis_api.connect()
        hass.http.register_view(TISEndPoint(tis_api))
        hass.http.register_view(ScanDevicesEndPoint(tis_api))
        hass.http.register_view(GetKeyEndpoint(tis_api))
    except ConnectionError as e:
        logging.error("error connecting to TIS api %s", e)
        return False
    # add the tis api to the hass data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return unload_ok

    return False


class TISEndPoint(HomeAssistantView):
    """TIS API endpoint."""

    url = "/api/tis"
    name = "api:tis"
    requires_auth = False

    def __init__(self, tis_api: TISApi) -> None:
        """Initialize the API endpoint."""
        self.api = tis_api

    async def post(self, request):
        """Handle the device publishing post request from the addon."""
        # Parse the JSON data from the request
        data = await request.json()
        # dump to file
        async with aiofiles.open("appliance_data.json", "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=4))

        # Start reload operations in the background
        _ = asyncio.create_task(self.reload_platforms())  # noqa: RUF006

        # Return the response immediately
        return web.json_response({"message": "success"})

    async def reload_platforms(self):
        """Reload the platforms."""
        # Reload the platforms
        for entry in self.api.hass.config_entries.async_entries(self.api.domain):
            await self.api.hass.config_entries.async_reload(entry.entry_id)


class ScanDevicesEndPoint(HomeAssistantView):
    """Scan Devices API endpoint."""

    url = "/api/scan_devices"
    name = "api:scan_devices"
    requires_auth = False

    def __init__(self, tis_api: TISApi) -> None:
        """Initialize the API endpoint."""
        self.api = tis_api
        self.discovery_packet: TISPacket = protocol_handler.generate_discovery_packet()

    async def get(self, request):
        """Handle the get request."""
        # Discover network devices
        devices = await self.discover_network_devices()
        devices = [
            {
                "device_id": device["device_id"],
                "device_type_code": device["device_type"],
                "device_type_name": self.api.devices_dict.get(
                    tuple(device["device_type"]), tuple(device["device_type"])
                ),
                "gateway": device["source_ip"],
            }
            for device in devices
        ]
        return web.json_response(devices)

    async def discover_network_devices(self, prodcast_attempts=10) -> list:
        """Discover TIS devices on network."""
        # empty current discovered devices list
        self.api.hass.data[self.api.domain]["discovered_devices"] = []
        for _ in range(prodcast_attempts):
            await self.api.protocol.sender.broadcast_packet(self.discovery_packet)
            await asyncio.sleep(1)

        return self.api.hass.data[self.api.domain]["discovered_devices"]


class GetKeyEndpoint(HomeAssistantView):
    """Get Key API endpoint."""

    url = "/api/get_key"
    name = "api:get_key"
    requires_auth = False

    def __init__(self, tis_api: TISApi) -> None:
        """Initialize the API endpoint."""
        self.api = tis_api

    async def get(self, request):
        """Handle the get key request."""
        # Get the MAC address
        mac = uuid.getnode()
        mac_address = ":".join(f"{mac:012X}"[i : i + 2] for i in range(0, 12, 2))
        # Return the MAC address
        return web.json_response({"key": mac_address})
