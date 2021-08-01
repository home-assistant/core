"""The SSDP integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import Any, Callable

from async_upnp_client.search import SSDPListener
from async_upnp_client.utils import CaseInsensitiveDict

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
)
from homeassistant.core import CoreState, HomeAssistant, callback as core_callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_ssdp, bind_hass

from .descriptions import DescriptionManager
from .flow import FlowDispatcher, SSDPFlow

DOMAIN = "ssdp"
SCAN_INTERVAL = timedelta(seconds=60)

IPV4_BROADCAST = IPv4Address("255.255.255.255")

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
    return scanner.async_get_discovery_info_by_udn_st(udn, st)


@bind_hass
def async_get_discovery_info_by_st(  # pylint: disable=invalid-name
    hass: HomeAssistant, st: str
) -> list[dict[str, str]]:
    """Fetch all the entries matching the st."""
    scanner: Scanner = hass.data[DOMAIN]
    return scanner.async_get_discovery_info_by_st(st)


@bind_hass
def async_get_discovery_info_by_udn(
    hass: HomeAssistant, udn: str
) -> list[dict[str, str]]:
    """Fetch all the entries matching the udn."""
    scanner: Scanner = hass.data[DOMAIN]
    return scanner.async_get_discovery_info_by_udn(udn)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SSDP integration."""

    scanner = hass.data[DOMAIN] = Scanner(hass, await async_get_ssdp(hass))

    asyncio.create_task(scanner.async_start())

    return True


@core_callback
def _async_use_default_interface(adapters: list[network.Adapter]) -> bool:
    for adapter in adapters:
        if adapter["enabled"] and not adapter["default"]:
            return False
    return True


@core_callback
def _async_process_callbacks(
    callbacks: list[Callable[[dict], None]], discovery_info: dict[str, str]
) -> None:
    for callback in callbacks:
        try:
            callback(discovery_info)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Failed to callback info: %s", discovery_info)


@core_callback
def _async_headers_match(
    headers: Mapping[str, str], match_dict: dict[str, str]
) -> bool:
    for header, val in match_dict.items():
        if val == MATCH_ALL:
            if header not in headers:
                return False
        elif headers.get(header) != val:
            return False
    return True


class Scanner:
    """Class to manage SSDP scanning."""

    def __init__(
        self, hass: HomeAssistant, integration_matchers: dict[str, list[dict[str, str]]]
    ) -> None:
        """Initialize class."""
        self.hass = hass
        self.seen: set[tuple[str, str | None]] = set()
        self.cache: dict[tuple[str, str], Mapping[str, str]] = {}
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
            for headers in self.cache.values():
                if _async_headers_match(headers, match_dict):
                    _async_process_callbacks(
                        [callback], self._async_headers_to_discovery_info(headers)
                    )

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
            try:
                IPv4Address(source_ip)
            except ValueError:
                continue
            # Some sonos devices only seem to respond if we send to the broadcast
            # address. This matches pysonos' behavior
            # https://github.com/amelchio/pysonos/blob/d4329b4abb657d106394ae69357805269708c996/pysonos/discovery.py#L120
            self._ssdp_listeners.append(
                SSDPListener(
                    async_callback=self._async_process_entry,
                    source_ip=source_ip,
                    target_ip=IPV4_BROADCAST,
                )
            )
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self.flow_dispatcher.async_start
        )
        results = await asyncio.gather(
            *(listener.async_start() for listener in self._ssdp_listeners),
            return_exceptions=True,
        )
        failed_listeners = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                _LOGGER.warning(
                    "Failed to setup listener for %s: %s",
                    self._ssdp_listeners[idx].source_ip,
                    result,
                )
                failed_listeners.append(self._ssdp_listeners[idx])
        for listener in failed_listeners:
            self._ssdp_listeners.remove(listener)
        self._cancel_scan = async_track_time_interval(
            self.hass, self.async_scan, SCAN_INTERVAL
        )

    @core_callback
    def _async_get_matching_callbacks(
        self, headers: Mapping[str, str]
    ) -> list[Callable[[dict], None]]:
        """Return a list of callbacks that match."""
        return [
            callback
            for callback, match_dict in self._callbacks
            if _async_headers_match(headers, match_dict)
        ]

    @core_callback
    def _async_matching_domains(self, info_with_req: CaseInsensitiveDict) -> set[str]:
        domains = set()
        for domain, matchers in self._integration_matchers.items():
            for matcher in matchers:
                if all(info_with_req.get(k) == v for (k, v) in matcher.items()):
                    domains.add(domain)
        return domains

    def _async_seen(self, header_st: str | None, header_location: str | None) -> bool:
        """Check if we have seen a specific st and optional location."""
        if header_st is None:
            return True
        return (header_st, header_location) in self.seen

    def _async_see(self, header_st: str | None, header_location: str | None) -> None:
        """Mark a specific st and optional location as seen."""
        if header_st is not None:
            self.seen.add((header_st, header_location))

    async def _async_process_entry(self, headers: Mapping[str, str]) -> None:
        """Process SSDP entries."""
        _LOGGER.debug("_async_process_entry: %s", headers)
        h_st = headers.get("st")
        h_location = headers.get("location")

        if h_st and (udn := _udn_from_usn(headers.get("usn"))):
            self.cache[(udn, h_st)] = headers

        callbacks = self._async_get_matching_callbacks(headers)
        if self._async_seen(h_st, h_location) and not callbacks:
            return

        assert self.description_manager is not None
        info_req = await self.description_manager.fetch_description(h_location) or {}
        info_with_req = CaseInsensitiveDict(**headers, **info_req)
        discovery_info = discovery_info_from_headers_and_request(info_with_req)

        _async_process_callbacks(callbacks, discovery_info)

        if self._async_seen(h_st, h_location):
            return
        self._async_see(h_st, h_location)

        for domain in self._async_matching_domains(info_with_req):
            _LOGGER.debug("Discovered %s at %s", domain, h_location)
            flow: SSDPFlow = {
                "domain": domain,
                "context": {"source": config_entries.SOURCE_SSDP},
                "data": discovery_info,
            }
            assert self.flow_dispatcher is not None
            self.flow_dispatcher.create(flow)

    @core_callback
    def _async_headers_to_discovery_info(
        self, headers: Mapping[str, str]
    ) -> dict[str, str]:
        """Combine the headers and description into discovery_info.

        Building this is a bit expensive so we only do it on demand.
        """
        assert self.description_manager is not None
        location = headers["location"]
        info_req = self.description_manager.async_cached_description(location) or {}
        return discovery_info_from_headers_and_request(
            CaseInsensitiveDict(**headers, **info_req)
        )

    @core_callback
    def async_get_discovery_info_by_udn_st(  # pylint: disable=invalid-name
        self, udn: str, st: str
    ) -> dict[str, str] | None:
        """Return discovery_info for a udn and st."""
        if headers := self.cache.get((udn, st)):
            return self._async_headers_to_discovery_info(headers)
        return None

    @core_callback
    def async_get_discovery_info_by_st(  # pylint: disable=invalid-name
        self, st: str
    ) -> list[dict[str, str]]:
        """Return matching discovery_infos for a st."""
        return [
            self._async_headers_to_discovery_info(headers)
            for udn_st, headers in self.cache.items()
            if udn_st[1] == st
        ]

    @core_callback
    def async_get_discovery_info_by_udn(self, udn: str) -> list[dict[str, str]]:
        """Return matching discovery_infos for a udn."""
        return [
            self._async_headers_to_discovery_info(headers)
            for udn_st, headers in self.cache.items()
            if udn_st[0] == udn
        ]


def discovery_info_from_headers_and_request(
    info_with_req: CaseInsensitiveDict,
) -> dict[str, str]:
    """Convert headers and description to discovery_info."""
    info = {DISCOVERY_MAPPING.get(k.lower(), k): v for k, v in info_with_req.items()}

    if ATTR_UPNP_UDN not in info and ATTR_SSDP_USN in info:
        if udn := _udn_from_usn(info[ATTR_SSDP_USN]):
            info[ATTR_UPNP_UDN] = udn

    return info


def _udn_from_usn(usn: str | None) -> str | None:
    """Get the UDN from the USN."""
    if usn is None:
        return None
    if usn.startswith("uuid:"):
        return usn.split("::")[0]
    return None
