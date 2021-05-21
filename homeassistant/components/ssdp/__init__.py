"""The SSDP integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import Any

import aiohttp
from async_upnp_client.ssdp import (
    SSDP_IP_V4,
    SSDP_IP_V6,
    SSDP_MX,
    SSDP_ST_ALL,
    SSDP_TARGET_V4,
    SsdpProtocol,
    build_ssdp_search_packet,
    get_ssdp_socket,
)
from defusedxml import ElementTree
from netdisco import ssdp, util

from homeassistant.components import network
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.loader import async_get_ssdp

DOMAIN = "ssdp"
SCAN_INTERVAL = timedelta(seconds=60)

# Attributes for accessing info from SSDP response
ATTR_SSDP_LOCATION = "ssdp_location"
ATTR_SSDP_ST = "ssdp_st"
ATTR_SSDP_USN = "ssdp_usn"
ATTR_SSDP_EXT = "ssdp_ext"
ATTR_SSDP_SERVER = "ssdp_server"
# Attributes for accessing info from retrieved UPnP device description
ATTR_UPNP_DEVICE_TYPE = "deviceType"
ATTR_UPNP_FRIENDLY_NAME = "friendlyName"
ATTR_UPNP_MANUFACTURER = "manufacturer"
ATTR_UPNP_MANUFACTURER_URL = "manufacturerURL"
ATTR_UPNP_MODEL_DESCRIPTION = "modelDescription"
ATTR_UPNP_MODEL_NAME = "modelName"
ATTR_UPNP_MODEL_NUMBER = "modelNumber"
ATTR_UPNP_MODEL_URL = "modelURL"
ATTR_UPNP_SERIAL = "serialNumber"
ATTR_UPNP_UDN = "UDN"
ATTR_UPNP_UPC = "UPC"
ATTR_UPNP_PRESENTATION_URL = "presentationURL"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the SSDP integration."""

    async def _async_initialize(_):
        scanner = Scanner(hass, await async_get_ssdp(hass))
        await scanner.async_scan(None)
        cancel_scan = async_track_time_interval(hass, scanner.async_scan, SCAN_INTERVAL)

        async def _async_stop_scans(event):
            cancel_scan()
            await scanner.async_stop()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_scans)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_initialize)

    return True


class SSDPListener:
    """Class to listen for SSDP."""

    def __init__(self, async_callback, source_ip):
        """Init the ssdp listener class."""
        self._async_callback = async_callback
        self._source_ip = source_ip
        self._targets = None
        self._transport = None

    @callback
    def async_search(self) -> None:
        """Start an SSDP search."""
        self._transport.sendto(
            build_ssdp_search_packet(SSDP_TARGET_V4, SSDP_MX, SSDP_ST_ALL), self._target
        )

    async def _async_on_data(self, request_line, headers) -> None:
        _LOGGER.debug("New data: %s %s", request_line, headers)
        await self._async_callback(headers)

    async def _async_on_connect(self, transport):
        self._transport = transport
        self.async_search()

    async def async_start(self):
        """Start the listener."""
        if isinstance(self._source_ip, IPv4Address):
            target_ip = IPv4Address(SSDP_IP_V4)
        else:
            target_ip = IPv6Address(SSDP_IP_V6)
        sock, source, self._target = get_ssdp_socket(self._source_ip, target_ip)
        sock.bind(source)
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            lambda: SsdpProtocol(
                loop, on_connect=self._async_on_connect, on_data=self._async_on_data
            ),
            sock=sock,
        )

    @callback
    def async_stop(self):
        """Stop the listener."""
        self._transport.close()


def _async_use_default_interface(adapters) -> bool:
    for adapter in adapters:
        if adapter["enabled"] and not adapter["default"]:
            return False
    return True


class Scanner:
    """Class to manage SSDP scanning."""

    def __init__(self, hass, integration_matchers):
        """Initialize class."""
        self.hass = hass
        self.seen = set()
        self._integration_matchers = integration_matchers
        self._description_cache = {}
        self._ssdp_listeners = []

    async def _async_on_ssdp_response(self, data: Mapping[str, Any]) -> None:
        """Process an ssdp response."""
        await self._async_process_entry(
            ssdp.UPNPEntry({key.lower(): item for key, item in data.items()})
        )

    @callback
    def async_store_entry(self, entry):
        """Save an entry for later processing."""
        self._entries.append(entry)

    async def async_stop(self):
        """Stop the scanner."""
        for listener in self._ssdp_listeners:
            listener.async_stop()
        self._ssdp_listeners = []

    async def _async_build_source_set(self):
        """Build the list of ssdp sources."""
        adapters = await network.async_get_adapters(self.hass)
        sources = set()
        if _async_use_default_interface(adapters):
            sources.add(IPv4Address("0.0.0.0"))
            return sources

        for adapter in adapters:
            if not adapter["enabled"]:
                continue
            if adapter["ipv4"]:
                ipv4 = adapter["ipv4"][0]
                sources.add(IPv4Address(ipv4["address"]))
            if adapter["ipv6"]:
                for ipv6 in adapter["ipv6"]:
                    sources.add(IPv6Address(f"::%{ipv6['scope_id']}"))

        return sources

    async def async_scan(self, *_):
        """Scan for new entries."""
        if self._ssdp_listeners:
            await asyncio.gather(
                *[listener.async_search() for listener in self._ssdp_listeners]
            )
            return

        for source_ip in await self._async_build_source_set():
            self._ssdp_listeners.append(
                SSDPListener(
                    async_callback=self._async_on_ssdp_response, source_ip=source_ip
                )
            )

        await asyncio.gather(
            *[listener.async_start() for listener in self._ssdp_listeners]
        )

    async def _async_process_entry(self, entry):
        """Process SSDP entries."""
        _LOGGER.debug("_async_process_entry: %s", entry)
        key = (entry.st, entry.location)
        if key in self.seen:
            return
        self.seen.add(key)

        if entry.location is not None and entry.location not in self._description_cache:
            try:
                result = await self._fetch_description(entry.location)
            except Exception:
                _LOGGER.exception("Failed to fetch ssdp data from: %s", entry.location)
                return
            else:
                self._description_cache[entry.location] = result

        info, domains = self._info_domains(entry)
        _LOGGER.debug("_info_domains: %s - %s", info, domains)

        for domain in domains:
            _LOGGER.debug("Discovered %s at %s", domain, entry.location)
            await self.hass.config_entries.flow.async_init(
                domain, context={"source": DOMAIN}, data=info
            )

    def _info_domains(self, entry):
        """Process a single entry."""

        info = {"st": entry.st}
        for key in "usn", "ext", "server":
            if key in entry.values:
                info[key] = entry.values[key]

        if entry.location:
            # Multiple entries usually share same location. Make sure
            # we fetch it only once.
            info_req = self._description_cache.get(entry.location)
            if info_req is None:
                return (None, [])

            info.update(info_req)

        domains = set()
        for domain, matchers in self._integration_matchers.items():
            for matcher in matchers:
                if all(info.get(k) == v for (k, v) in matcher.items()):
                    domains.add(domain)

        if domains:
            return (info_from_entry(entry, info), domains)

        return (None, [])

    async def _fetch_description(self, xml_location):
        """Fetch an XML description."""
        session = self.hass.helpers.aiohttp_client.async_get_clientsession()
        try:
            for _ in range(2):
                resp = await session.get(xml_location, timeout=5)
                xml = await resp.text(errors="replace")
                # Samsung Smart TV sometimes returns an empty document the
                # first time. Retry once.
                if xml:
                    break
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Error fetching %s: %s", xml_location, err)
            return {}

        try:
            tree = ElementTree.fromstring(xml)
        except ElementTree.ParseError as err:
            _LOGGER.debug("Error parsing %s: %s", xml_location, err)
            return {}

        return util.etree_to_dict(tree).get("root", {}).get("device", {})


def info_from_entry(entry, device_info):
    """Get info from an entry."""
    info = {
        ATTR_SSDP_LOCATION: entry.location,
        ATTR_SSDP_ST: entry.st,
    }
    if device_info:
        info.update(device_info)
        info.pop("st", None)
        if "usn" in info:
            info[ATTR_SSDP_USN] = info.pop("usn")
        if "ext" in info:
            info[ATTR_SSDP_EXT] = info.pop("ext")
        if "server" in info:
            info[ATTR_SSDP_SERVER] = info.pop("server")

    return info
