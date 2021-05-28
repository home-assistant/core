"""The SSDP integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import Any, Callable

from async_upnp_client.search import SSDPListener

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, HomeAssistant, callback as core_callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
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


DISCOVERY_MAPPING = {
    "usn": ATTR_SSDP_USN,
    "ext": ATTR_SSDP_EXT,
    "server": ATTR_SSDP_SERVER,
    "st": ATTR_SSDP_ST,
    "location": ATTR_SSDP_LOCATION,
}


_LOGGER = logging.getLogger(__name__)


@bind_hass
def async_register_callback(
    hass: HomeAssistant,
    callback: Callable[[dict], None],
    match_dict: None | dict[str, str] = None,
) -> Callable[[], None]:
    """Register to receive a callback on ssdp broadcast.

    Returns a callback that can be used to cancel the registration.
    """
    scanner: Scanner = hass.data[DOMAIN]
    return scanner.async_register_callback(callback, match_dict)


@bind_hass
def async_get_discovery_info_by_udn_st(  # pylint: disable=invalid-name
    hass: HomeAssistant, udn: str, st: str
) -> dict[str, str] | None:
    """Fetch the discovery info cache."""
    scanner: Scanner = hass.data[DOMAIN]
    return scanner.cache.get((udn, st))


@bind_hass
def async_get_discovery_info_by_st(  # pylint: disable=invalid-name
    hass: HomeAssistant, st: str
) -> dict[str, dict[str, str]]:
    """Fetch all the udns for the st."""
    scanner: Scanner = hass.data[DOMAIN]
    return {
        udn_st[0]: discovery_info
        for udn_st, discovery_info in scanner.cache.items()
        if udn_st[1] == st
    }


@bind_hass
def async_get_discovery_info_by_udn(
    hass: HomeAssistant, udn: str
) -> dict[str, dict[str, str]]:
    """Fetch all the sts for the udn."""
    scanner: Scanner = hass.data[DOMAIN]
    return {
        udn_st[1]: discovery_info
        for udn_st, discovery_info in scanner.cache.items()
        if udn_st[0] == udn
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SSDP integration."""

    scanner = hass.data[DOMAIN] = Scanner(hass, await async_get_ssdp(hass))

    asyncio.create_task(scanner.async_start())

    return True


def _async_use_default_interface(adapters: list[network.Adapter]) -> bool:
    for adapter in adapters:
        if adapter["enabled"] and not adapter["default"]:
            return False
    return True


def _callback_if_match(
    callback: Callable[[dict], None], info: dict[str, str], match_dict: dict[str, str]
) -> None:
    """Fire a callback if info matches the match dict."""
    if not all(info.get(k) == v for (k, v) in match_dict.items()):
        return
    try:
        callback(info)
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Failed to callback info: %s", info)


class Scanner:
    """Class to manage SSDP scanning."""

    def __init__(
        self, hass: HomeAssistant, integration_matchers: dict[str, list[dict[str, str]]]
    ) -> None:
        """Initialize class."""
        self.hass = hass
        self.seen: set[tuple[str, str]] = set()
        self.cache: dict[tuple[str, str], dict[str, str]] = {}
        self._integration_matchers = integration_matchers
        self._cancel_scan: Callable[[], None] | None = None
        self._ssdp_listeners: list[SSDPListener] = []
        self._callbacks: list[tuple[Callable[[dict], None], dict[str, str]]] = []
        self.flow_dispatcher: FlowDispatcher | None = None
        self.description_manager: DescriptionManager | None = None

    @core_callback
    def async_register_callback(
        self, callback: Callable[[dict], None], match_dict: None | dict[str, str] = None
    ) -> Callable[[], None]:
        """Register a callback."""
        if match_dict is None:
            match_dict = {}

        # Make sure any entries that happened
        # before the callback was registered are fired
        if self.hass.state != CoreState.running:
            for info in self.cache.values():
                _callback_if_match(callback, info, match_dict)

        callback_entry = (callback, match_dict)
        self._callbacks.append(callback_entry)

        @core_callback
        def _async_remove_callback() -> None:
            self._callbacks.remove(callback_entry)

        return _async_remove_callback

    @core_callback
    def async_stop(self, *_: Any) -> None:
        """Stop the scanner."""
        assert self._cancel_scan is not None
        self._cancel_scan()
        for listener in self._ssdp_listeners:
            listener.async_stop()
        self._ssdp_listeners = []

    async def _async_build_source_set(self) -> set[IPv4Address | IPv6Address]:
        """Build the list of ssdp sources."""
        adapters = await network.async_get_adapters(self.hass)
        sources: set[IPv4Address | IPv6Address] = set()
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
                ipv6 = adapter["ipv6"][0]
                # With python 3.9 add scope_ids can be
                # added by enumerating adapter["ipv6"]s
                # IPv6Address(f"::%{ipv6['scope_id']}")
                sources.add(IPv6Address(ipv6["address"]))

        return sources

    @core_callback
    def async_scan(self, *_: Any) -> None:
        """Scan for new entries."""
        for listener in self._ssdp_listeners:
            listener.async_search()

    async def async_start(self) -> None:
        """Start the scanner."""
        self.description_manager = DescriptionManager(self.hass)
        self.flow_dispatcher = FlowDispatcher(self.hass)
        for source_ip in await self._async_build_source_set():
            self._ssdp_listeners.append(
                SSDPListener(
                    async_callback=self._async_process_entry, source_ip=source_ip
                )
            )

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self.flow_dispatcher.async_start
        )
        await asyncio.gather(
            *[listener.async_start() for listener in self._ssdp_listeners]
        )
        self._cancel_scan = async_track_time_interval(
            self.hass, self.async_scan, SCAN_INTERVAL
        )

    async def _async_process_entry(self, headers: Mapping[str, str]) -> None:
        """Process SSDP entries."""
        _LOGGER.debug("_async_process_entry: %s", headers)
        if "st" not in headers or "location" not in headers:
            return
        assert self.description_manager is not None

        info_with_req = dict(headers)
        info_req = await self.description_manager.fetch_description(headers["location"])
        if info_req:
            info_with_req.update(info_req)

        discovery_info = discovery_info_from_headers_and_request(info_with_req)

        if udn := discovery_info.get(ATTR_UPNP_UDN):
            self.cache[(udn, headers["st"])] = discovery_info

        for callback, match_dict in self._callbacks:
            _callback_if_match(callback, discovery_info, match_dict)

        key = (headers["st"], headers["location"])
        if key in self.seen:
            return
        self.seen.add(key)

        domains = set()
        for domain, matchers in self._integration_matchers.items():
            for matcher in matchers:
                if all(info_with_req.get(k) == v for (k, v) in matcher.items()):
                    domains.add(domain)

        for domain in domains:
            _LOGGER.debug("Discovered %s at %s", domain, headers["location"])
            flow: SSDPFlow = {
                "domain": domain,
                "context": {"source": config_entries.SOURCE_SSDP},
                "data": discovery_info,
            }
            assert self.flow_dispatcher is not None
            self.flow_dispatcher.create(flow)


def discovery_info_from_headers_and_request(data: dict[str, str]) -> dict[str, str]:
    """Get info from an entry."""
    info = {
        **{k: v for k, v in data.items() if k not in DISCOVERY_MAPPING},
        **{
            discovery_key: data[header]
            for header, discovery_key in DISCOVERY_MAPPING.items()
            if header in data
        },
    }

    if ATTR_UPNP_UDN not in info and str(info.get(ATTR_SSDP_USN)).startswith("uuid:"):
        info[ATTR_UPNP_UDN] = str(info[ATTR_SSDP_USN]).split("::")[0]

    return info
