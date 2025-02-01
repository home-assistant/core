"""The SSDP integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping
from datetime import timedelta
from enum import Enum
from functools import partial
from ipaddress import IPv4Address, IPv6Address
import logging
import socket
from time import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.const import (
    AddressTupleVXType,
    DeviceIcon,
    DeviceInfo,
    DeviceOrServiceType,
    SsdpSource,
)
from async_upnp_client.description_cache import DescriptionCache
from async_upnp_client.server import UpnpServer, UpnpServerDevice, UpnpServerService
from async_upnp_client.ssdp import (
    SSDP_PORT,
    determine_source_target,
    fix_ipv6_address_scope_id,
    is_ipv4_address,
)
from async_upnp_client.ssdp_listener import SsdpDevice, SsdpDeviceTracker, SsdpListener
from async_upnp_client.utils import CaseInsensitiveDict

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
    __version__ as current_version,
)
from homeassistant.core import Event, HassJob, HomeAssistant, callback as core_callback
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.instance_id import async_get as async_get_instance_id
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.service_info.ssdp import (
    ATTR_NT as _ATTR_NT,
    ATTR_ST as _ATTR_ST,
    ATTR_UPNP_DEVICE_TYPE as _ATTR_UPNP_DEVICE_TYPE,
    ATTR_UPNP_FRIENDLY_NAME as _ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER as _ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MANUFACTURER_URL as _ATTR_UPNP_MANUFACTURER_URL,
    ATTR_UPNP_MODEL_DESCRIPTION as _ATTR_UPNP_MODEL_DESCRIPTION,
    ATTR_UPNP_MODEL_NAME as _ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_MODEL_NUMBER as _ATTR_UPNP_MODEL_NUMBER,
    ATTR_UPNP_MODEL_URL as _ATTR_UPNP_MODEL_URL,
    ATTR_UPNP_PRESENTATION_URL as _ATTR_UPNP_PRESENTATION_URL,
    ATTR_UPNP_SERIAL as _ATTR_UPNP_SERIAL,
    ATTR_UPNP_SERVICE_LIST as _ATTR_UPNP_SERVICE_LIST,
    ATTR_UPNP_UDN as _ATTR_UPNP_UDN,
    ATTR_UPNP_UPC as _ATTR_UPNP_UPC,
    SsdpServiceInfo as _SsdpServiceInfo,
)
from homeassistant.helpers.system_info import async_get_system_info
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_ssdp, bind_hass
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.logging import catch_log_exception

DOMAIN = "ssdp"
SSDP_SCANNER = "scanner"
UPNP_SERVER = "server"
UPNP_SERVER_MIN_PORT = 40000
UPNP_SERVER_MAX_PORT = 40100
SCAN_INTERVAL = timedelta(minutes=10)

IPV4_BROADCAST = IPv4Address("255.255.255.255")

# Attributes for accessing info from SSDP response
ATTR_SSDP_LOCATION = "ssdp_location"
ATTR_SSDP_ST = "ssdp_st"
ATTR_SSDP_NT = "ssdp_nt"
ATTR_SSDP_UDN = "ssdp_udn"
ATTR_SSDP_USN = "ssdp_usn"
ATTR_SSDP_EXT = "ssdp_ext"
ATTR_SSDP_SERVER = "ssdp_server"
ATTR_SSDP_BOOTID = "BOOTID.UPNP.ORG"
ATTR_SSDP_NEXTBOOTID = "NEXTBOOTID.UPNP.ORG"
# Attributes for accessing info from retrieved UPnP device description
_DEPRECATED_ATTR_ST = DeprecatedConstant(
    _ATTR_ST,
    "homeassistant.helpers.service_info.ssdp.ATTR_ST",
    "2026.2",
)
_DEPRECATED_ATTR_NT = DeprecatedConstant(
    _ATTR_NT,
    "homeassistant.helpers.service_info.ssdp.ATTR_NT",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_DEVICE_TYPE = DeprecatedConstant(
    _ATTR_UPNP_DEVICE_TYPE,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_DEVICE_TYPE",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_FRIENDLY_NAME = DeprecatedConstant(
    _ATTR_UPNP_FRIENDLY_NAME,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_FRIENDLY_NAME",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_MANUFACTURER = DeprecatedConstant(
    _ATTR_UPNP_MANUFACTURER,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_MANUFACTURER",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_MANUFACTURER_URL = DeprecatedConstant(
    _ATTR_UPNP_MANUFACTURER_URL,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_MANUFACTURER_URL",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_MODEL_DESCRIPTION = DeprecatedConstant(
    _ATTR_UPNP_MODEL_DESCRIPTION,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_MODEL_DESCRIPTION",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_MODEL_NAME = DeprecatedConstant(
    _ATTR_UPNP_MODEL_NAME,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_MODEL_NAME",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_MODEL_NUMBER = DeprecatedConstant(
    _ATTR_UPNP_MODEL_NUMBER,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_MODEL_NUMBER",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_MODEL_URL = DeprecatedConstant(
    _ATTR_UPNP_MODEL_URL,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_MODEL_URL",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_SERIAL = DeprecatedConstant(
    _ATTR_UPNP_SERIAL,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_SERIAL",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_SERVICE_LIST = DeprecatedConstant(
    _ATTR_UPNP_SERVICE_LIST,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_SERVICE_LIST",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_UDN = DeprecatedConstant(
    _ATTR_UPNP_UDN,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_UDN",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_UPC = DeprecatedConstant(
    _ATTR_UPNP_UPC,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_UPC",
    "2026.2",
)
_DEPRECATED_ATTR_UPNP_PRESENTATION_URL = DeprecatedConstant(
    _ATTR_UPNP_PRESENTATION_URL,
    "homeassistant.helpers.service_info.ssdp.ATTR_UPNP_PRESENTATION_URL",
    "2026.2",
)
# Attributes for accessing info added by Home Assistant
ATTR_HA_MATCHING_DOMAINS = "x_homeassistant_matching_domains"

PRIMARY_MATCH_KEYS = [
    _ATTR_UPNP_MANUFACTURER,
    _ATTR_ST,
    _ATTR_UPNP_DEVICE_TYPE,
    _ATTR_NT,
    _ATTR_UPNP_MANUFACTURER_URL,
]

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_DEPRECATED_SsdpServiceInfo = DeprecatedConstant(
    _SsdpServiceInfo,
    "homeassistant.helpers.service_info.ssdp.SsdpServiceInfo",
    "2026.2",
)


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


def _format_err(name: str, *args: Any) -> str:
    """Format error message."""
    return f"Exception in SSDP callback {name}: {args}"


@bind_hass
async def async_register_callback(
    hass: HomeAssistant,
    callback: Callable[
        [_SsdpServiceInfo, SsdpChange], Coroutine[Any, Any, None] | None
    ],
    match_dict: dict[str, str] | None = None,
) -> Callable[[], None]:
    """Register to receive a callback on ssdp broadcast.

    Returns a callback that can be used to cancel the registration.
    """
    scanner: Scanner = hass.data[DOMAIN][SSDP_SCANNER]
    job = HassJob(
        catch_log_exception(
            callback,
            partial(_format_err, str(callback)),
        ),
        f"ssdp callback {match_dict}",
    )
    return await scanner.async_register_callback(job, match_dict)


@bind_hass
async def async_get_discovery_info_by_udn_st(
    hass: HomeAssistant, udn: str, st: str
) -> _SsdpServiceInfo | None:
    """Fetch the discovery info cache."""
    scanner: Scanner = hass.data[DOMAIN][SSDP_SCANNER]
    return await scanner.async_get_discovery_info_by_udn_st(udn, st)


@bind_hass
async def async_get_discovery_info_by_st(
    hass: HomeAssistant, st: str
) -> list[_SsdpServiceInfo]:
    """Fetch all the entries matching the st."""
    scanner: Scanner = hass.data[DOMAIN][SSDP_SCANNER]
    return await scanner.async_get_discovery_info_by_st(st)


@bind_hass
async def async_get_discovery_info_by_udn(
    hass: HomeAssistant, udn: str
) -> list[_SsdpServiceInfo]:
    """Fetch all the entries matching the udn."""
    scanner: Scanner = hass.data[DOMAIN][SSDP_SCANNER]
    return await scanner.async_get_discovery_info_by_udn(udn)


async def async_build_source_set(hass: HomeAssistant) -> set[IPv4Address | IPv6Address]:
    """Build the list of ssdp sources."""
    return {
        source_ip
        for source_ip in await network.async_get_enabled_source_ips(hass)
        if not source_ip.is_loopback
        and not source_ip.is_global
        and ((source_ip.version == 6 and source_ip.scope_id) or source_ip.version == 4)
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SSDP integration."""

    integration_matchers = IntegrationMatchers()
    integration_matchers.async_setup(await async_get_ssdp(hass))

    scanner = Scanner(hass, integration_matchers)
    server = Server(hass)
    hass.data[DOMAIN] = {
        SSDP_SCANNER: scanner,
        UPNP_SERVER: server,
    }

    await scanner.async_start()
    await server.async_start()

    return True


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


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
