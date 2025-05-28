"""The SSDP integration server."""

from __future__ import annotations

import asyncio
import logging
import socket
from time import time
from typing import Any
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

from async_upnp_client.const import AddressTupleVXType, DeviceIcon, DeviceInfo
from async_upnp_client.server import UpnpServer, UpnpServerDevice, UpnpServerService
from async_upnp_client.ssdp import (
    determine_source_target,
    fix_ipv6_address_scope_id,
    is_ipv4_address,
)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    __version__ as current_version,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.instance_id import async_get as async_get_instance_id
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.system_info import async_get_system_info

from .common import async_build_source_set

UPNP_SERVER_MIN_PORT = 40000
UPNP_SERVER_MAX_PORT = 40100

_LOGGER = logging.getLogger(__name__)


class HassUpnpServiceDevice(UpnpServerDevice):
    """Hass Device."""

    DEVICE_DEFINITION = DeviceInfo(
        device_type="urn:home-assistant.io:device:HomeAssistant:1",
        friendly_name="filled_later_on",
        manufacturer="Home Assistant",
        manufacturer_url="https://www.home-assistant.io",
        model_description=None,
        model_name="filled_later_on",
        model_number=current_version,
        model_url="https://www.home-assistant.io",
        serial_number="filled_later_on",
        udn="filled_later_on",
        upc=None,
        presentation_url="https://my.home-assistant.io/",
        url="/device.xml",
        icons=[
            DeviceIcon(
                mimetype="image/png",
                width=1024,
                height=1024,
                depth=24,
                url="/static/icons/favicon-1024x1024.png",
            ),
            DeviceIcon(
                mimetype="image/png",
                width=512,
                height=512,
                depth=24,
                url="/static/icons/favicon-512x512.png",
            ),
            DeviceIcon(
                mimetype="image/png",
                width=384,
                height=384,
                depth=24,
                url="/static/icons/favicon-384x384.png",
            ),
            DeviceIcon(
                mimetype="image/png",
                width=192,
                height=192,
                depth=24,
                url="/static/icons/favicon-192x192.png",
            ),
        ],
        xml=ET.Element("server_device"),
    )
    EMBEDDED_DEVICES: list[type[UpnpServerDevice]] = []
    SERVICES: list[type[UpnpServerService]] = []


async def _async_find_next_available_port(source: AddressTupleVXType) -> int:
    """Get a free TCP port."""
    family = socket.AF_INET if is_ipv4_address(source) else socket.AF_INET6
    test_socket = socket.socket(family, socket.SOCK_STREAM)
    test_socket.setblocking(False)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    for port in range(UPNP_SERVER_MIN_PORT, UPNP_SERVER_MAX_PORT):
        addr = (source[0],) + (port,) + source[2:]
        try:
            test_socket.bind(addr)
        except OSError:
            if port == UPNP_SERVER_MAX_PORT - 1:
                raise
        else:
            return port

    raise RuntimeError("unreachable")


class Server:
    """Class to be visible via SSDP searching and advertisements."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize class."""
        self.hass = hass
        self._upnp_servers: list[UpnpServer] = []

    async def async_start(self) -> None:
        """Start the server."""
        bus = self.hass.bus
        bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED,
            self._async_start_upnp_servers,
        )

    async def _async_get_instance_udn(self) -> str:
        """Get Unique Device Name for this instance."""
        instance_id = await async_get_instance_id(self.hass)
        return f"uuid:{instance_id[0:8]}-{instance_id[8:12]}-{instance_id[12:16]}-{instance_id[16:20]}-{instance_id[20:32]}".upper()

    async def _async_start_upnp_servers(self, event: Event) -> None:
        """Start the UPnP/SSDP servers."""
        # Update UDN with our instance UDN.
        udn = await self._async_get_instance_udn()
        system_info = await async_get_system_info(self.hass)
        model_name = system_info["installation_type"]
        try:
            presentation_url = get_url(self.hass, allow_ip=True, prefer_external=False)
        except NoURLAvailableError:
            _LOGGER.warning(
                "Could not set up UPnP/SSDP server, as a presentation URL could"
                " not be determined; Please configure your internal URL"
                " in the Home Assistant general configuration"
            )
            return

        serial_number = await async_get_instance_id(self.hass)
        HassUpnpServiceDevice.DEVICE_DEFINITION = (
            HassUpnpServiceDevice.DEVICE_DEFINITION._replace(
                udn=udn,
                friendly_name=f"{self.hass.config.location_name} (Home Assistant)",
                model_name=model_name,
                presentation_url=presentation_url,
                serial_number=serial_number,
            )
        )

        # Update icon URLs.
        for index, icon in enumerate(HassUpnpServiceDevice.DEVICE_DEFINITION.icons):
            new_url = urljoin(presentation_url, icon.url)
            HassUpnpServiceDevice.DEVICE_DEFINITION.icons[index] = icon._replace(
                url=new_url
            )

        # Start a server on all source IPs.
        boot_id = int(time())
        for source_ip in await async_build_source_set(self.hass):
            source_ip_str = str(source_ip)
            if source_ip.version == 6:
                assert source_ip.scope_id is not None
                source_tuple: AddressTupleVXType = (
                    source_ip_str,
                    0,
                    0,
                    int(source_ip.scope_id),
                )
            else:
                source_tuple = (source_ip_str, 0)
            source, target = determine_source_target(source_tuple)
            source = fix_ipv6_address_scope_id(source) or source
            http_port = await _async_find_next_available_port(source)
            _LOGGER.debug("Binding UPnP HTTP server to: %s:%s", source_ip, http_port)
            self._upnp_servers.append(
                UpnpServer(
                    source=source,
                    target=target,
                    http_port=http_port,
                    server_device=HassUpnpServiceDevice,
                    boot_id=boot_id,
                )
            )
        results = await asyncio.gather(
            *(upnp_server.async_start() for upnp_server in self._upnp_servers),
            return_exceptions=True,
        )
        failed_servers = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                _LOGGER.debug(
                    "Failed to setup server for %s: %s",
                    self._upnp_servers[idx].source,
                    result,
                )
                failed_servers.append(self._upnp_servers[idx])
        for server in failed_servers:
            self._upnp_servers.remove(server)

    async def async_stop(self, *_: Any) -> None:
        """Stop the server."""
        await self._async_stop_upnp_servers()

    async def _async_stop_upnp_servers(self) -> None:
        """Stop UPnP/SSDP servers."""
        for server in self._upnp_servers:
            await server.async_stop()
