"""Support for exposing Home Assistant via Zeroconf."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from contextlib import suppress
import fnmatch
import ipaddress
import logging
import socket
from typing import Any, TypedDict, cast

import voluptuous as vol
from zeroconf import InterfaceChoice, IPVersion, ServiceStateChange
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.components.network import async_get_source_ip
from homeassistant.components.network.models import Adapter
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    __version__,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.loader import async_get_homekit, async_get_zeroconf, bind_hass

from .models import HaAsyncServiceBrowser, HaAsyncZeroconf, HaZeroconf
from .usage import install_multiple_zeroconf_catcher

_LOGGER = logging.getLogger(__name__)

DOMAIN = "zeroconf"

ZEROCONF_TYPE = "_home-assistant._tcp.local."
HOMEKIT_TYPES = [
    "_hap._tcp.local.",
    # Thread based devices
    "_hap._udp.local.",
]

CONF_DEFAULT_INTERFACE = "default_interface"
CONF_IPV6 = "ipv6"
DEFAULT_DEFAULT_INTERFACE = True
DEFAULT_IPV6 = True

HOMEKIT_PAIRED_STATUS_FLAG = "sf"
HOMEKIT_MODEL = "md"

MDNS_TARGET_IP = "224.0.0.251"

# Property key=value has a max length of 255
# so we use 230 to leave space for key=
MAX_PROPERTY_VALUE_LEN = 230

# Dns label max length
MAX_NAME_LEN = 63

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_DEFAULT_INTERFACE),
            cv.deprecated(CONF_IPV6),
            vol.Schema(
                {
                    vol.Optional(CONF_DEFAULT_INTERFACE): cv.boolean,
                    vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class HaServiceInfo(TypedDict):
    """Prepared info from mDNS entries."""

    host: str
    port: int | None
    hostname: str
    type: str
    name: str
    properties: dict[str, Any]


class ZeroconfFlow(TypedDict):
    """A queued zeroconf discovery flow."""

    domain: str
    context: dict[str, Any]
    data: HaServiceInfo


@bind_hass
async def async_get_instance(hass: HomeAssistant) -> HaZeroconf:
    """Zeroconf instance to be shared with other integrations that use it."""
    return cast(HaZeroconf, (await _async_get_instance(hass)).zeroconf)


@bind_hass
async def async_get_async_instance(hass: HomeAssistant) -> HaAsyncZeroconf:
    """Zeroconf instance to be shared with other integrations that use it."""
    return await _async_get_instance(hass)


async def _async_get_instance(hass: HomeAssistant, **zcargs: Any) -> HaAsyncZeroconf:
    if DOMAIN in hass.data:
        return cast(HaAsyncZeroconf, hass.data[DOMAIN])

    logging.getLogger("zeroconf").setLevel(logging.NOTSET)

    zeroconf = HaZeroconf(**zcargs)
    aio_zc = HaAsyncZeroconf(zc=zeroconf)

    install_multiple_zeroconf_catcher(zeroconf)

    async def _async_stop_zeroconf(_event: Event) -> None:
        """Stop Zeroconf."""
        await aio_zc.ha_async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_zeroconf)
    hass.data[DOMAIN] = aio_zc

    return aio_zc


def _async_use_default_interface(adapters: list[Adapter]) -> bool:
    for adapter in adapters:
        if adapter["enabled"] and not adapter["default"]:
            return False
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Zeroconf and make Home Assistant discoverable."""
    zc_args: dict = {}

    adapters = await network.async_get_adapters(hass)

    ipv6 = True
    if not any(adapter["enabled"] and adapter["ipv6"] for adapter in adapters):
        ipv6 = False
        zc_args["ip_version"] = IPVersion.V4Only
    else:
        zc_args["ip_version"] = IPVersion.All

    if not ipv6 and _async_use_default_interface(adapters):
        zc_args["interfaces"] = InterfaceChoice.Default
    else:
        interfaces = zc_args["interfaces"] = []
        for adapter in adapters:
            if not adapter["enabled"]:
                continue
            if ipv4s := adapter["ipv4"]:
                interfaces.extend(
                    ipv4["address"]
                    for ipv4 in ipv4s
                    if not ipaddress.ip_address(ipv4["address"]).is_loopback
                )
            if adapter["ipv6"] and adapter["index"] not in interfaces:
                interfaces.append(adapter["index"])

    aio_zc = await _async_get_instance(hass, **zc_args)
    zeroconf = cast(HaZeroconf, aio_zc.zeroconf)
    zeroconf_types, homekit_models = await asyncio.gather(
        async_get_zeroconf(hass), async_get_homekit(hass)
    )
    discovery = ZeroconfDiscovery(hass, zeroconf, zeroconf_types, homekit_models, ipv6)
    await discovery.async_setup()

    async def _async_zeroconf_hass_start(_event: Event) -> None:
        """Expose Home Assistant on zeroconf when it starts.

        Wait till started or otherwise HTTP is not up and running.
        """
        uuid = await hass.helpers.instance_id.async_get()
        await _async_register_hass_zc_service(hass, aio_zc, uuid)

    @callback
    def _async_start_discovery(_event: Event) -> None:
        """Start processing flows."""
        discovery.async_start()

    async def _async_zeroconf_hass_stop(_event: Event) -> None:
        await discovery.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_zeroconf_hass_stop)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_zeroconf_hass_start)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_start_discovery)

    return True


def _get_announced_addresses(
    adapters: list[Adapter],
    first_ip: bytes | None = None,
) -> list[bytes]:
    """Return a list of IP addresses to announce via zeroconf.

    If first_ip is not None, it will be the first address in the list.
    """
    addresses = {
        addr.packed
        for addr in [
            ipaddress.ip_address(ip["address"])
            for adapter in adapters
            if adapter["enabled"]
            for ip in cast(list, adapter["ipv6"]) + cast(list, adapter["ipv4"])
        ]
        if not (addr.is_unspecified or addr.is_loopback)
    }
    if first_ip:
        address_list = [first_ip]
        address_list.extend(addresses - set({first_ip}))
    else:
        address_list = list(addresses)
    return address_list


async def _async_register_hass_zc_service(
    hass: HomeAssistant, aio_zc: HaAsyncZeroconf, uuid: str
) -> None:
    # Get instance UUID
    valid_location_name = _truncate_location_name_to_valid(hass.config.location_name)

    params = {
        "location_name": valid_location_name,
        "uuid": uuid,
        "version": __version__,
        "external_url": "",
        "internal_url": "",
        # Old base URL, for backward compatibility
        "base_url": "",
        # Always needs authentication
        "requires_api_password": True,
    }

    # Get instance URL's
    with suppress(NoURLAvailableError):
        params["external_url"] = get_url(hass, allow_internal=False)

    with suppress(NoURLAvailableError):
        params["internal_url"] = get_url(hass, allow_external=False)

    # Set old base URL based on external or internal
    params["base_url"] = params["external_url"] or params["internal_url"]

    adapters = await network.async_get_adapters(hass)

    # Puts the default IPv4 address first in the list to preserve compatibility,
    # because some mDNS implementations ignores anything but the first announced address.
    host_ip = await async_get_source_ip(hass, target_ip=MDNS_TARGET_IP)
    host_ip_pton = None
    if host_ip:
        host_ip_pton = socket.inet_pton(socket.AF_INET, host_ip)
    address_list = _get_announced_addresses(adapters, host_ip_pton)

    _suppress_invalid_properties(params)

    info = AsyncServiceInfo(
        ZEROCONF_TYPE,
        name=f"{valid_location_name}.{ZEROCONF_TYPE}",
        server=f"{uuid}.local.",
        addresses=address_list,
        port=hass.http.server_port,
        properties=params,
    )

    _LOGGER.info("Starting Zeroconf broadcast")
    await aio_zc.async_register_service(info, allow_name_change=True)


class FlowDispatcher:
    """Dispatch discovery flows."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the discovery dispatcher."""
        self.hass = hass
        self.pending_flows: list[ZeroconfFlow] = []
        self.started = False

    @callback
    def async_start(self) -> None:
        """Start processing pending flows."""
        self.started = True
        self.hass.loop.call_soon(self._async_process_pending_flows)

    def _async_process_pending_flows(self) -> None:
        for flow in self.pending_flows:
            self.hass.async_create_task(self._init_flow(flow))
        self.pending_flows = []

    def async_create(self, flow: ZeroconfFlow) -> None:
        """Create and add or queue a flow."""
        if self.started:
            self.hass.async_create_task(self._init_flow(flow))
        else:
            self.pending_flows.append(flow)

    def _init_flow(self, flow: ZeroconfFlow) -> Coroutine[None, None, FlowResult]:
        """Create a flow."""
        return self.hass.config_entries.flow.async_init(
            flow["domain"], context=flow["context"], data=flow["data"]
        )


class ZeroconfDiscovery:
    """Discovery via zeroconf."""

    def __init__(
        self,
        hass: HomeAssistant,
        zeroconf: HaZeroconf,
        zeroconf_types: dict[str, list[dict[str, str]]],
        homekit_models: dict[str, str],
        ipv6: bool,
    ) -> None:
        """Init discovery."""
        self.hass = hass
        self.zeroconf = zeroconf
        self.zeroconf_types = zeroconf_types
        self.homekit_models = homekit_models
        self.ipv6 = ipv6

        self.flow_dispatcher: FlowDispatcher | None = None
        self.async_service_browser: HaAsyncServiceBrowser | None = None

    async def async_setup(self) -> None:
        """Start discovery."""
        self.flow_dispatcher = FlowDispatcher(self.hass)
        types = list(self.zeroconf_types)
        # We want to make sure we know about other HomeAssistant
        # instances as soon as possible to avoid name conflicts
        # so we always browse for ZEROCONF_TYPE
        for hk_type in (ZEROCONF_TYPE, *HOMEKIT_TYPES):
            if hk_type not in self.zeroconf_types:
                types.append(hk_type)
        _LOGGER.debug("Starting Zeroconf browser for: %s", types)
        self.async_service_browser = HaAsyncServiceBrowser(
            self.ipv6, self.zeroconf, types, handlers=[self.async_service_update]
        )

    async def async_stop(self) -> None:
        """Cancel the service browser and stop processing the queue."""
        if self.async_service_browser:
            await self.async_service_browser.async_cancel()

    @callback
    def async_start(self) -> None:
        """Start processing discovery flows."""
        assert self.flow_dispatcher is not None
        self.flow_dispatcher.async_start()

    @callback
    def async_service_update(
        self,
        zeroconf: HaZeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Service state changed."""
        _LOGGER.debug(
            "service_update: type=%s name=%s state_change=%s",
            service_type,
            name,
            state_change,
        )

        if state_change == ServiceStateChange.Removed:
            return

        asyncio.create_task(self._process_service_update(zeroconf, service_type, name))

    async def _process_service_update(
        self, zeroconf: HaZeroconf, service_type: str, name: str
    ) -> None:
        """Process a zeroconf update."""
        async_service_info = AsyncServiceInfo(service_type, name)
        await async_service_info.async_request(zeroconf, 3000)

        info = info_from_service(async_service_info)
        if not info:
            # Prevent the browser thread from collapsing
            _LOGGER.debug("Failed to get addresses for device %s", name)
            return

        _LOGGER.debug("Discovered new device %s %s", name, info)
        assert self.flow_dispatcher is not None

        # If we can handle it as a HomeKit discovery, we do that here.
        if service_type in HOMEKIT_TYPES:
            if pending_flow := handle_homekit(self.hass, self.homekit_models, info):
                self.flow_dispatcher.async_create(pending_flow)
            # Continue on here as homekit_controller
            # still needs to get updates on devices
            # so it can see when the 'c#' field is updated.
            #
            # We only send updates to homekit_controller
            # if the device is already paired in order to avoid
            # offering a second discovery for the same device
            if pending_flow and HOMEKIT_PAIRED_STATUS_FLAG in info["properties"]:
                try:
                    # 0 means paired and not discoverable by iOS clients)
                    if int(info["properties"][HOMEKIT_PAIRED_STATUS_FLAG]):
                        return
                except ValueError:
                    # HomeKit pairing status unknown
                    # likely bad homekit data
                    return

        if "name" in info:
            lowercase_name: str | None = info["name"].lower()
        else:
            lowercase_name = None

        if "macaddress" in info["properties"]:
            uppercase_mac: str | None = info["properties"]["macaddress"].upper()
        else:
            uppercase_mac = None

        if "manufacturer" in info["properties"]:
            lowercase_manufacturer: str | None = info["properties"][
                "manufacturer"
            ].lower()
        else:
            lowercase_manufacturer = None

        # Not all homekit types are currently used for discovery
        # so not all service type exist in zeroconf_types
        for matcher in self.zeroconf_types.get(service_type, []):
            if len(matcher) > 1:
                if "macaddress" in matcher and (
                    uppercase_mac is None
                    or not fnmatch.fnmatch(uppercase_mac, matcher["macaddress"])
                ):
                    continue
                if "name" in matcher and (
                    lowercase_name is None
                    or not fnmatch.fnmatch(lowercase_name, matcher["name"])
                ):
                    continue
                if "manufacturer" in matcher and (
                    lowercase_manufacturer is None
                    or not fnmatch.fnmatch(
                        lowercase_manufacturer, matcher["manufacturer"]
                    )
                ):
                    continue

            flow: ZeroconfFlow = {
                "domain": matcher["domain"],
                "context": {"source": config_entries.SOURCE_ZEROCONF},
                "data": info,
            }
            self.flow_dispatcher.async_create(flow)


def handle_homekit(
    hass: HomeAssistant, homekit_models: dict[str, str], info: HaServiceInfo
) -> ZeroconfFlow | None:
    """Handle a HomeKit discovery.

    Return if discovery was forwarded.
    """
    model = None
    props = info["properties"]

    for key in props:
        if key.lower() == HOMEKIT_MODEL:
            model = props[key]
            break

    if model is None:
        return None

    for test_model in homekit_models:
        if (
            model != test_model
            and not model.startswith((f"{test_model} ", f"{test_model}-"))
            and not fnmatch.fnmatch(model, test_model)
        ):
            continue

        return {
            "domain": homekit_models[test_model],
            "context": {"source": config_entries.SOURCE_HOMEKIT},
            "data": info,
        }

    return None


def info_from_service(service: AsyncServiceInfo) -> HaServiceInfo | None:
    """Return prepared info from mDNS entries."""
    properties: dict[str, Any] = {"_raw": {}}

    for key, value in service.properties.items():
        # See https://ietf.org/rfc/rfc6763.html#section-6.4 and
        # https://ietf.org/rfc/rfc6763.html#section-6.5 for expected encodings
        # for property keys and values
        try:
            key = key.decode("ascii")
        except UnicodeDecodeError:
            _LOGGER.debug(
                "Ignoring invalid key provided by [%s]: %s", service.name, key
            )
            continue

        properties["_raw"][key] = value

        with suppress(UnicodeDecodeError):
            if isinstance(value, bytes):
                properties[key] = value.decode("utf-8")

    if not service.addresses:
        return None

    address = service.addresses[0]

    return {
        "host": str(ipaddress.ip_address(address)),
        "port": service.port,
        "hostname": service.server,
        "type": service.type,
        "name": service.name,
        "properties": properties,
    }


def _suppress_invalid_properties(properties: dict) -> None:
    """Suppress any properties that will cause zeroconf to fail to startup."""

    for prop, prop_value in properties.items():
        if not isinstance(prop_value, str):
            continue

        if len(prop_value.encode("utf-8")) > MAX_PROPERTY_VALUE_LEN:
            _LOGGER.error(
                "The property '%s' was suppressed because it is longer than the maximum length of %d bytes: %s",
                prop,
                MAX_PROPERTY_VALUE_LEN,
                prop_value,
            )
            properties[prop] = ""


def _truncate_location_name_to_valid(location_name: str) -> str:
    """Truncate or return the location name usable for zeroconf."""
    if len(location_name.encode("utf-8")) < MAX_NAME_LEN:
        return location_name

    _LOGGER.warning(
        "The location name was truncated because it is longer than the maximum length of %d bytes: %s",
        MAX_NAME_LEN,
        location_name,
    )
    return location_name.encode("utf-8")[:MAX_NAME_LEN].decode("utf-8", "ignore")
