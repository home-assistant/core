"""The SSDP integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import Any

from netdisco import ssdp
from ssdp.listener import SSDPListener

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.loader import async_get_ssdp, bind_hass

from .descriptions import DescriptionManager
from .flow import FlowDispatcher, SSDPFlow

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


@bind_hass
def async_register_callback(hass, callback, match_dict=None):
    """Register to receive a callback on ssdp broadcast.

    Returns a callback that can be used to cancel the registration.
    """
    return hass.data[DOMAIN].async_register_callback(callback, match_dict)


async def async_setup(hass, config):
    """Set up the SSDP integration."""

    scanner = hass.data[DOMAIN] = Scanner(hass, await async_get_ssdp(hass))

    asyncio.create_task(scanner.async_start())

    return True


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
        self._cancel_scan = None
        self._ssdp_listeners = []
        self._callbacks = []
        self.flow_dispatcher: FlowDispatcher | None = None

    async def _async_on_ssdp_response(self, data: Mapping[str, Any]) -> None:
        """Process an ssdp response."""
        await self._async_process_entry(
            ssdp.UPNPEntry({key.lower(): item for key, item in data.items()})
        )

    @callback
    def async_register_callback(self, ssdp_callback, match_dict=None):
        """Register a callback."""
        if match_dict is None:
            match_dict = {}

        callback_entry = (ssdp_callback, match_dict)
        self._callbacks.append(callback_entry)

        @callback
        def _async_remove_callback():
            self._callbacks.remove(callback_entry)

        return _async_remove_callback

    @callback
    def async_store_entry(self, entry):
        """Save an entry for later processing."""
        self._entries.append(entry)

    @callback
    def async_stop(self, *_):
        """Stop the scanner."""
        self._cancel_scan()
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
            if not adapter["ipv6"]:
                continue
            for ipv6 in adapter["ipv6"]:
                sources.add(IPv6Address(f"::%{ipv6['scope_id']}"))

        return sources

    @callback
    def async_scan(self, *_):
        """Scan for new entries."""
        if self._ssdp_listeners:
            for listener in self._ssdp_listeners:
                listener.async_search()
            return

    async def async_start(self):
        """Start the scanner."""
        self.description_manager = DescriptionManager(self.hass)
        self.flow_dispatcher = FlowDispatcher(self.hass)
        for source_ip in await self._async_build_source_set():
            self._ssdp_listeners.append(
                SSDPListener(
                    async_callback=self._async_on_ssdp_response, source_ip=source_ip
                )
            )

        await asyncio.gather(
            *[listener.async_start() for listener in self._ssdp_listeners]
        )

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self.flow_dispatcher.async_start
        )
        self._cancel_scan = async_track_time_interval(
            self.hass, self.async_scan, SCAN_INTERVAL
        )

    async def _async_process_entry(self, entry):
        """Process SSDP entries."""
        _LOGGER.debug("_async_process_entry: %s", entry)
        key = (entry.st, entry.location)
        info_req = await self.description_manager.fetch_description(entry.location)
        info, domains = self._info_domains(entry, info_req)

        for ssdp_callback, match_dict in self._callbacks:
            if not all(item in info.items() for item in match_dict.items()):
                continue
            try:
                ssdp_callback(info)
            except Exception:
                _LOGGER.exception("Failed to callback info: %s", info)
                continue

        if key in self.seen:
            return
        self.seen.add(key)

        for domain in domains:
            _LOGGER.debug("Discovered %s at %s", domain, entry.location)
            flow: SSDPFlow = {
                "domain": domain,
                "context": {"source": config_entries.SOURCE_SSDP},
                "data": info,
            }
            self.flow_dispatcher.create(flow)

    def _info_domains(self, entry, info_req):
        """Process a single entry."""

        info = {"st": entry.st}
        for key in "usn", "ext", "server":
            if key in entry.values:
                info[key] = entry.values[key]

        if info_req:
            info.update(info_req)

        domains = set()
        for domain, matchers in self._integration_matchers.items():
            for matcher in matchers:
                if all(info.get(k) == v for (k, v) in matcher.items()):
                    domains.add(domain)

        return info_from_entry(entry, info), domains


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
