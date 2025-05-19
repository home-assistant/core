"""The SSDP integration scanner."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping
from datetime import timedelta
from enum import Enum
from ipaddress import IPv4Address
import logging
from typing import TYPE_CHECKING, Any

from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.const import AddressTupleVXType, DeviceOrServiceType, SsdpSource
from async_upnp_client.description_cache import DescriptionCache
from async_upnp_client.ssdp import (
    SSDP_PORT,
    determine_source_target,
    fix_ipv6_address_scope_id,
    is_ipv4_address,
)
from async_upnp_client.ssdp_listener import SsdpDevice, SsdpDeviceTracker, SsdpListener
from async_upnp_client.utils import CaseInsensitiveDict

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, MATCH_ALL
from homeassistant.core import HassJob, HomeAssistant, callback as core_callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service_info.ssdp import (
    ATTR_NT as _ATTR_NT,
    ATTR_ST as _ATTR_ST,
    ATTR_UPNP_DEVICE_TYPE as _ATTR_UPNP_DEVICE_TYPE,
    ATTR_UPNP_MANUFACTURER as _ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MANUFACTURER_URL as _ATTR_UPNP_MANUFACTURER_URL,
    ATTR_UPNP_UDN as _ATTR_UPNP_UDN,
    SsdpServiceInfo as _SsdpServiceInfo,
)
from homeassistant.util.async_ import create_eager_task

from .common import async_build_source_set
from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=10)

IPV4_BROADCAST = IPv4Address("255.255.255.255")


PRIMARY_MATCH_KEYS = [
    _ATTR_UPNP_MANUFACTURER,
    _ATTR_ST,
    _ATTR_UPNP_DEVICE_TYPE,
    _ATTR_NT,
    _ATTR_UPNP_MANUFACTURER_URL,
]

_LOGGER = logging.getLogger(__name__)


SsdpChange = Enum("SsdpChange", "ALIVE BYEBYE UPDATE")
type SsdpHassJobCallback = HassJob[
    [_SsdpServiceInfo, SsdpChange], Coroutine[Any, Any, None] | None
]

SSDP_SOURCE_SSDP_CHANGE_MAPPING: Mapping[SsdpSource, SsdpChange] = {
    SsdpSource.SEARCH_ALIVE: SsdpChange.ALIVE,
    SsdpSource.SEARCH_CHANGED: SsdpChange.ALIVE,
    SsdpSource.ADVERTISEMENT_ALIVE: SsdpChange.ALIVE,
    SsdpSource.ADVERTISEMENT_BYEBYE: SsdpChange.BYEBYE,
    SsdpSource.ADVERTISEMENT_UPDATE: SsdpChange.UPDATE,
}


@core_callback
def _async_process_callbacks(
    hass: HomeAssistant,
    callbacks: list[SsdpHassJobCallback],
    discovery_info: _SsdpServiceInfo,
    ssdp_change: SsdpChange,
) -> None:
    for callback in callbacks:
        try:
            hass.async_run_hass_job(
                callback, discovery_info, ssdp_change, background=True
            )
        except Exception:
            _LOGGER.exception("Failed to callback info: %s", discovery_info)


@core_callback
def _async_headers_match(
    headers: CaseInsensitiveDict, lower_match_dict: dict[str, str]
) -> bool:
    for header, val in lower_match_dict.items():
        if val == MATCH_ALL:
            if header not in headers:
                return False
        elif headers.get_lower(header) != val:
            return False
    return True


class IntegrationMatchers:
    """Optimized integration matching."""

    def __init__(self) -> None:
        """Init optimized integration matching."""
        self._match_by_key: (
            dict[str, dict[str, list[tuple[str, dict[str, str]]]]] | None
        ) = None

    @core_callback
    def async_setup(
        self, integration_matchers: dict[str, list[dict[str, str]]]
    ) -> None:
        """Build matchers by key.

        Here we convert the primary match keys into their own
        dicts so we can do lookups of the primary match
        key to find the match dict.
        """
        self._match_by_key = {}
        for key in PRIMARY_MATCH_KEYS:
            matchers_by_key = self._match_by_key[key] = {}
            for domain, matchers in integration_matchers.items():
                for matcher in matchers:
                    if match_value := matcher.get(key):
                        matchers_by_key.setdefault(match_value, []).append(
                            (domain, matcher)
                        )

    @core_callback
    def async_matching_domains(self, info_with_desc: CaseInsensitiveDict) -> set[str]:
        """Find domains matching the passed CaseInsensitiveDict."""
        assert self._match_by_key is not None
        return {
            domain
            for key, matchers_by_key in self._match_by_key.items()
            if (match_value := info_with_desc.get(key))
            for domain, matcher in matchers_by_key.get(match_value, ())
            if info_with_desc.items() >= matcher.items()
        }


class Scanner:
    """Class to manage SSDP searching and SSDP advertisements."""

    def __init__(
        self, hass: HomeAssistant, integration_matchers: IntegrationMatchers
    ) -> None:
        """Initialize class."""
        self.hass = hass
        self._cancel_scan: Callable[[], None] | None = None
        self._ssdp_listeners: list[SsdpListener] = []
        self._device_tracker = SsdpDeviceTracker()
        self._callbacks: list[tuple[SsdpHassJobCallback, dict[str, str]]] = []
        self._description_cache: DescriptionCache | None = None
        self.integration_matchers = integration_matchers

    @property
    def _ssdp_devices(self) -> list[SsdpDevice]:
        """Get all seen devices."""
        return list(self._device_tracker.devices.values())

    async def async_register_callback(
        self, callback: SsdpHassJobCallback, match_dict: dict[str, str] | None = None
    ) -> Callable[[], None]:
        """Register a callback."""
        if match_dict is None:
            lower_match_dict = {}
        else:
            lower_match_dict = {k.lower(): v for k, v in match_dict.items()}

        # Make sure any entries that happened
        # before the callback was registered are fired
        for ssdp_device in self._ssdp_devices:
            for headers in ssdp_device.all_combined_headers.values():
                if _async_headers_match(headers, lower_match_dict):
                    _async_process_callbacks(
                        self.hass,
                        [callback],
                        await self._async_headers_to_discovery_info(
                            ssdp_device, headers
                        ),
                        SsdpChange.ALIVE,
                    )

        callback_entry = (callback, lower_match_dict)
        self._callbacks.append(callback_entry)

        @core_callback
        def _async_remove_callback() -> None:
            self._callbacks.remove(callback_entry)

        return _async_remove_callback

    async def async_stop(self, *_: Any) -> None:
        """Stop the scanner."""
        assert self._cancel_scan is not None
        self._cancel_scan()

        await self._async_stop_ssdp_listeners()

    async def _async_stop_ssdp_listeners(self) -> None:
        """Stop the SSDP listeners."""
        await asyncio.gather(
            *(
                create_eager_task(listener.async_stop())
                for listener in self._ssdp_listeners
            ),
            return_exceptions=True,
        )

    async def async_scan(self, *_: Any) -> None:
        """Scan for new entries using ssdp listeners."""
        await self.async_scan_multicast()
        await self.async_scan_broadcast()

    async def async_scan_multicast(self, *_: Any) -> None:
        """Scan for new entries using multicase target."""
        for ssdp_listener in self._ssdp_listeners:
            await ssdp_listener.async_search()

    async def async_scan_broadcast(self, *_: Any) -> None:
        """Scan for new entries using broadcast target."""
        # Some sonos devices only seem to respond if we send to the broadcast
        # address. This matches pysonos' behavior
        # https://github.com/amelchio/pysonos/blob/d4329b4abb657d106394ae69357805269708c996/pysonos/discovery.py#L120
        for listener in self._ssdp_listeners:
            if is_ipv4_address(listener.source):
                await listener.async_search((str(IPV4_BROADCAST), SSDP_PORT))

    async def async_start(self) -> None:
        """Start the scanners."""
        session = async_get_clientsession(self.hass, verify_ssl=False)
        requester = AiohttpSessionRequester(session, True, 10)
        self._description_cache = DescriptionCache(requester)

        await self._async_start_ssdp_listeners()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_stop)
        self._cancel_scan = async_track_time_interval(
            self.hass, self.async_scan, SCAN_INTERVAL, name="SSDP scanner"
        )

        async_dispatcher_connect(
            self.hass,
            config_entries.signal_discovered_config_entry_removed(DOMAIN),
            self._handle_config_entry_removed,
        )

        # Trigger the initial-scan.
        await self.async_scan()

    async def _async_start_ssdp_listeners(self) -> None:
        """Start the SSDP Listeners."""
        # Devices are shared between all sources.
        for source_ip in await async_build_source_set(self.hass):
            source_ip_str = str(source_ip)
            if source_ip.version == 6:
                source_tuple: AddressTupleVXType = (
                    source_ip_str,
                    0,
                    0,
                    int(getattr(source_ip, "scope_id")),
                )
            else:
                source_tuple = (source_ip_str, 0)
            source, target = determine_source_target(source_tuple)
            source = fix_ipv6_address_scope_id(source) or source
            self._ssdp_listeners.append(
                SsdpListener(
                    callback=self._ssdp_listener_callback,
                    source=source,
                    target=target,
                    device_tracker=self._device_tracker,
                )
            )
        results = await asyncio.gather(
            *(
                create_eager_task(listener.async_start())
                for listener in self._ssdp_listeners
            ),
            return_exceptions=True,
        )
        failed_listeners = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                _LOGGER.debug(
                    "Failed to setup listener for %s: %s",
                    self._ssdp_listeners[idx].source,
                    result,
                )
                failed_listeners.append(self._ssdp_listeners[idx])
        for listener in failed_listeners:
            self._ssdp_listeners.remove(listener)

    @core_callback
    def _async_get_matching_callbacks(
        self,
        combined_headers: CaseInsensitiveDict,
    ) -> list[SsdpHassJobCallback]:
        """Return a list of callbacks that match."""
        return [
            callback
            for callback, lower_match_dict in self._callbacks
            if _async_headers_match(combined_headers, lower_match_dict)
        ]

    def _ssdp_listener_callback(
        self,
        ssdp_device: SsdpDevice,
        dst: DeviceOrServiceType,
        source: SsdpSource,
    ) -> None:
        """Handle a device/service change."""
        _LOGGER.debug(
            "SSDP: ssdp_device: %s, dst: %s, source: %s", ssdp_device, dst, source
        )

        assert self._description_cache

        location = ssdp_device.location
        _, info_desc = self._description_cache.peek_description_dict(location)
        if info_desc is None:
            # Fetch info desc in separate task and process from there.
            self.hass.async_create_background_task(
                self._ssdp_listener_process_callback_with_lookup(
                    ssdp_device, dst, source
                ),
                name=f"ssdp_info_desc_lookup_{location}",
                eager_start=True,
            )
            return

        # Info desc known, process directly.
        self._ssdp_listener_process_callback(ssdp_device, dst, source, info_desc)

    async def _ssdp_listener_process_callback_with_lookup(
        self,
        ssdp_device: SsdpDevice,
        dst: DeviceOrServiceType,
        source: SsdpSource,
    ) -> None:
        """Handle a device/service change."""
        location = ssdp_device.location
        self._ssdp_listener_process_callback(
            ssdp_device,
            dst,
            source,
            await self._async_get_description_dict(location),
        )

    def _ssdp_listener_process_callback(
        self,
        ssdp_device: SsdpDevice,
        dst: DeviceOrServiceType,
        source: SsdpSource,
        info_desc: Mapping[str, Any],
        skip_callbacks: bool = False,
    ) -> None:
        """Handle a device/service change."""
        matching_domains: set[str] = set()
        combined_headers = ssdp_device.combined_headers(dst)
        callbacks = self._async_get_matching_callbacks(combined_headers)

        # If there are no changes from a search, do not trigger a config flow
        if source != SsdpSource.SEARCH_ALIVE:
            matching_domains = self.integration_matchers.async_matching_domains(
                CaseInsensitiveDict(combined_headers.as_dict(), **info_desc)
            )

        if (
            not callbacks
            and not matching_domains
            and source != SsdpSource.ADVERTISEMENT_BYEBYE
        ):
            return

        discovery_info = discovery_info_from_headers_and_description(
            ssdp_device, combined_headers, info_desc
        )
        discovery_info.x_homeassistant_matching_domains = matching_domains

        if callbacks and not skip_callbacks:
            ssdp_change = SSDP_SOURCE_SSDP_CHANGE_MAPPING[source]
            _async_process_callbacks(self.hass, callbacks, discovery_info, ssdp_change)

        # Config flows should only be created for alive/update messages from alive devices
        if source == SsdpSource.ADVERTISEMENT_BYEBYE:
            self._async_dismiss_discoveries(discovery_info)
            return

        _LOGGER.debug("Discovery info: %s", discovery_info)

        if not matching_domains:
            return  # avoid creating DiscoveryKey if there are no matches

        discovery_key = discovery_flow.DiscoveryKey(
            domain=DOMAIN, key=ssdp_device.udn, version=1
        )
        for domain in matching_domains:
            _LOGGER.debug("Discovered %s at %s", domain, ssdp_device.location)
            discovery_flow.async_create_flow(
                self.hass,
                domain,
                {"source": config_entries.SOURCE_SSDP},
                discovery_info,
                discovery_key=discovery_key,
            )

    def _async_dismiss_discoveries(
        self, byebye_discovery_info: _SsdpServiceInfo
    ) -> None:
        """Dismiss all discoveries for the given address."""
        for flow in self.hass.config_entries.flow.async_progress_by_init_data_type(
            _SsdpServiceInfo,
            lambda service_info: bool(
                service_info.ssdp_st == byebye_discovery_info.ssdp_st
                and service_info.ssdp_location == byebye_discovery_info.ssdp_location
            ),
        ):
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

    async def _async_get_description_dict(
        self, location: str | None
    ) -> Mapping[str, str]:
        """Get description dict."""
        assert self._description_cache is not None
        cache = self._description_cache

        has_description, description = cache.peek_description_dict(location)
        if has_description:
            return description or {}

        return await cache.async_get_description_dict(location) or {}

    async def _async_headers_to_discovery_info(
        self, ssdp_device: SsdpDevice, headers: CaseInsensitiveDict
    ) -> _SsdpServiceInfo:
        """Combine the headers and description into discovery_info.

        Building this is a bit expensive so we only do it on demand.
        """
        location = headers["location"]
        info_desc = await self._async_get_description_dict(location)
        return discovery_info_from_headers_and_description(
            ssdp_device, headers, info_desc
        )

    async def async_get_discovery_info_by_udn_st(
        self, udn: str, st: str
    ) -> _SsdpServiceInfo | None:
        """Return discovery_info for a udn and st."""
        for ssdp_device in self._ssdp_devices:
            if ssdp_device.udn == udn:
                if headers := ssdp_device.combined_headers(st):
                    return await self._async_headers_to_discovery_info(
                        ssdp_device, headers
                    )
        return None

    async def async_get_discovery_info_by_st(self, st: str) -> list[_SsdpServiceInfo]:
        """Return matching discovery_infos for a st."""
        return [
            await self._async_headers_to_discovery_info(ssdp_device, headers)
            for ssdp_device in self._ssdp_devices
            if (headers := ssdp_device.combined_headers(st))
        ]

    async def async_get_discovery_info_by_udn(self, udn: str) -> list[_SsdpServiceInfo]:
        """Return matching discovery_infos for a udn."""
        return [
            await self._async_headers_to_discovery_info(ssdp_device, headers)
            for ssdp_device in self._ssdp_devices
            for headers in ssdp_device.all_combined_headers.values()
            if ssdp_device.udn == udn
        ]

    @core_callback
    def _handle_config_entry_removed(
        self,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Handle config entry changes."""
        if TYPE_CHECKING:
            assert self._description_cache is not None
        cache = self._description_cache
        for discovery_key in entry.discovery_keys[DOMAIN]:
            if discovery_key.version != 1 or not isinstance(discovery_key.key, str):
                continue
            udn = discovery_key.key
            _LOGGER.debug("Rediscover service %s", udn)

            for ssdp_device in self._ssdp_devices:
                if ssdp_device.udn != udn:
                    continue
                for dst in ssdp_device.all_combined_headers:
                    has_cached_desc, info_desc = cache.peek_description_dict(
                        ssdp_device.location
                    )
                    if has_cached_desc and info_desc:
                        self._ssdp_listener_process_callback(
                            ssdp_device,
                            dst,
                            SsdpSource.SEARCH,
                            info_desc,
                            True,  # Skip integration callbacks
                        )


def discovery_info_from_headers_and_description(
    ssdp_device: SsdpDevice,
    combined_headers: CaseInsensitiveDict,
    info_desc: Mapping[str, Any],
) -> _SsdpServiceInfo:
    """Convert headers and description to discovery_info."""
    ssdp_usn = combined_headers["usn"]
    ssdp_st = combined_headers.get_lower("st")
    if isinstance(info_desc, CaseInsensitiveDict):
        upnp_info = {**info_desc.as_dict()}
    else:
        upnp_info = {**info_desc}

    # Increase compatibility: depending on the message type,
    # either the ST (Search Target, from M-SEARCH messages)
    # or NT (Notification Type, from NOTIFY messages) header is mandatory
    if not ssdp_st:
        ssdp_st = combined_headers["nt"]

    # Ensure UPnP "udn" is set
    if _ATTR_UPNP_UDN not in upnp_info:
        if udn := _udn_from_usn(ssdp_usn):
            upnp_info[_ATTR_UPNP_UDN] = udn

    return _SsdpServiceInfo(
        ssdp_usn=ssdp_usn,
        ssdp_st=ssdp_st,
        ssdp_ext=combined_headers.get_lower("ext"),
        ssdp_server=combined_headers.get_lower("server"),
        ssdp_location=combined_headers.get_lower("location"),
        ssdp_udn=combined_headers.get_lower("_udn"),
        ssdp_nt=combined_headers.get_lower("nt"),
        ssdp_headers=combined_headers,
        upnp=upnp_info,
        ssdp_all_locations=set(ssdp_device.locations),
    )


def _udn_from_usn(usn: str | None) -> str | None:
    """Get the UDN from the USN."""
    if usn is None:
        return None
    if usn.startswith("uuid:"):
        return usn.split("::")[0]
    return None
