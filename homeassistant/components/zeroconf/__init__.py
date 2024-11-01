"""Support for exposing Home Assistant via Zeroconf."""

from __future__ import annotations

import contextlib
from contextlib import suppress
from dataclasses import dataclass
from fnmatch import translate
from functools import lru_cache
from ipaddress import IPv4Address, IPv6Address
import logging
import re
import sys
from typing import TYPE_CHECKING, Any, Final, cast

import voluptuous as vol
from zeroconf import (
    BadTypeInNameException,
    InterfaceChoice,
    IPVersion,
    ServiceStateChange,
)
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import (
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_STOP,
    __version__,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers import discovery_flow, instance_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import (
    HomeKitDiscoveredIntegration,
    ZeroconfMatcher,
    async_get_homekit,
    async_get_zeroconf,
    bind_hass,
)
from homeassistant.setup import async_when_setup_or_start

from .models import HaAsyncZeroconf, HaZeroconf
from .usage import install_multiple_zeroconf_catcher

_LOGGER = logging.getLogger(__name__)

DOMAIN = "zeroconf"

ZEROCONF_TYPE = "_home-assistant._tcp.local."
HOMEKIT_TYPES = [
    "_hap._tcp.local.",
    # Thread based devices
    "_hap._udp.local.",
]
_HOMEKIT_MODEL_SPLITS = (None, " ", "-")


CONF_DEFAULT_INTERFACE = "default_interface"
CONF_IPV6 = "ipv6"
DEFAULT_DEFAULT_INTERFACE = True
DEFAULT_IPV6 = True

HOMEKIT_PAIRED_STATUS_FLAG = "sf"
HOMEKIT_MODEL_LOWER = "md"
HOMEKIT_MODEL_UPPER = "MD"

# Property key=value has a max length of 255
# so we use 230 to leave space for key=
MAX_PROPERTY_VALUE_LEN = 230

# Dns label max length
MAX_NAME_LEN = 63

ATTR_DOMAIN: Final = "domain"
ATTR_NAME: Final = "name"
ATTR_PROPERTIES: Final = "properties"

# Attributes for ZeroconfServiceInfo[ATTR_PROPERTIES]
ATTR_PROPERTIES_ID: Final = "id"

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


@dataclass(slots=True)
class ZeroconfServiceInfo(BaseServiceInfo):
    """Prepared info from mDNS entries.

    The ip_address is the most recently updated address
    that is not a link local or unspecified address.

    The ip_addresses are all addresses in order of most
    recently updated to least recently updated.

    The host is the string representation of the ip_address.

    The addresses are the string representations of the
    ip_addresses.

    It is recommended to use the ip_address to determine
    the address to connect to as it will be the most
    recently updated address that is not a link local
    or unspecified address.
    """

    ip_address: IPv4Address | IPv6Address
    ip_addresses: list[IPv4Address | IPv6Address]
    port: int | None
    hostname: str
    type: str
    name: str
    properties: dict[str, Any]

    @property
    def host(self) -> str:
        """Return the host."""
        return str(self.ip_address)

    @property
    def addresses(self) -> list[str]:
        """Return the addresses."""
        return [str(ip_address) for ip_address in self.ip_addresses]


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

    # Wait to the close event to shutdown zeroconf to give
    # integrations time to send a good bye message
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_stop_zeroconf)
    hass.data[DOMAIN] = aio_zc

    return aio_zc


@callback
def _async_zc_has_functional_dual_stack() -> bool:
    """Return true for platforms not supporting IP_ADD_MEMBERSHIP on an AF_INET6 socket.

    Zeroconf only supports a single listen socket at this time.
    """
    return not sys.platform.startswith("freebsd") and not sys.platform.startswith(
        "darwin"
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Zeroconf and make Home Assistant discoverable."""
    zc_args: dict = {"ip_version": IPVersion.V4Only}

    adapters = await network.async_get_adapters(hass)

    ipv6 = False
    if _async_zc_has_functional_dual_stack():
        if any(adapter["enabled"] and adapter["ipv6"] for adapter in adapters):
            ipv6 = True
            zc_args["ip_version"] = IPVersion.All
    elif not any(adapter["enabled"] and adapter["ipv4"] for adapter in adapters):
        zc_args["ip_version"] = IPVersion.V6Only
        ipv6 = True

    if not ipv6 and network.async_only_default_interface_enabled(adapters):
        zc_args["interfaces"] = InterfaceChoice.Default
    else:
        zc_args["interfaces"] = [
            str(source_ip)
            for source_ip in await network.async_get_enabled_source_ips(hass)
            if not source_ip.is_loopback
            and not (isinstance(source_ip, IPv6Address) and source_ip.is_global)
            and not (
                isinstance(source_ip, IPv6Address)
                and zc_args["ip_version"] == IPVersion.V4Only
            )
            and not (
                isinstance(source_ip, IPv4Address)
                and zc_args["ip_version"] == IPVersion.V6Only
            )
        ]

    aio_zc = await _async_get_instance(hass, **zc_args)
    zeroconf = cast(HaZeroconf, aio_zc.zeroconf)
    zeroconf_types = await async_get_zeroconf(hass)
    homekit_models = await async_get_homekit(hass)
    homekit_model_lookup, homekit_model_matchers = _build_homekit_model_lookups(
        homekit_models
    )
    discovery = ZeroconfDiscovery(
        hass,
        zeroconf,
        zeroconf_types,
        homekit_model_lookup,
        homekit_model_matchers,
    )
    await discovery.async_setup()

    async def _async_zeroconf_hass_start(hass: HomeAssistant, comp: str) -> None:
        """Expose Home Assistant on zeroconf when it starts.

        Wait till started or otherwise HTTP is not up and running.
        """
        uuid = await instance_id.async_get(hass)
        await _async_register_hass_zc_service(hass, aio_zc, uuid)

    async def _async_zeroconf_hass_stop(_event: Event) -> None:
        await discovery.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_zeroconf_hass_stop)
    async_when_setup_or_start(hass, "frontend", _async_zeroconf_hass_start)

    return True


def _build_homekit_model_lookups(
    homekit_models: dict[str, HomeKitDiscoveredIntegration],
) -> tuple[
    dict[str, HomeKitDiscoveredIntegration],
    dict[re.Pattern, HomeKitDiscoveredIntegration],
]:
    """Build lookups for homekit models."""
    homekit_model_lookup: dict[str, HomeKitDiscoveredIntegration] = {}
    homekit_model_matchers: dict[re.Pattern, HomeKitDiscoveredIntegration] = {}

    for model, discovery in homekit_models.items():
        if "*" in model or "?" in model or "[" in model:
            homekit_model_matchers[_compile_fnmatch(model)] = discovery
        else:
            homekit_model_lookup[model] = discovery

    return homekit_model_lookup, homekit_model_matchers


def _filter_disallowed_characters(name: str) -> str:
    """Filter disallowed characters from a string.

    . is a reversed character for zeroconf.
    """
    return name.replace(".", " ")


async def _async_register_hass_zc_service(
    hass: HomeAssistant, aio_zc: HaAsyncZeroconf, uuid: str
) -> None:
    # Get instance UUID
    valid_location_name = _truncate_location_name_to_valid(
        _filter_disallowed_characters(hass.config.location_name or "Home")
    )

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

    _suppress_invalid_properties(params)

    info = AsyncServiceInfo(
        ZEROCONF_TYPE,
        name=f"{valid_location_name}.{ZEROCONF_TYPE}",
        server=f"{uuid}.local.",
        parsed_addresses=await network.async_get_announce_addresses(hass),
        port=hass.http.server_port,
        properties=params,
    )

    _LOGGER.info("Starting Zeroconf broadcast")
    await aio_zc.async_register_service(info, allow_name_change=True)


def _match_against_props(matcher: dict[str, str], props: dict[str, str | None]) -> bool:
    """Check a matcher to ensure all values in props."""
    for key, value in matcher.items():
        prop_val = props.get(key)
        if prop_val is None or not _memorized_fnmatch(prop_val.lower(), value):
            return False
    return True


def is_homekit_paired(props: dict[str, Any]) -> bool:
    """Check properties to see if a device is homekit paired."""
    if HOMEKIT_PAIRED_STATUS_FLAG not in props:
        return False
    with contextlib.suppress(ValueError):
        # 0 means paired and not discoverable by iOS clients)
        return int(props[HOMEKIT_PAIRED_STATUS_FLAG]) == 0
    # If we cannot tell, we assume its not paired
    return False


class ZeroconfDiscovery:
    """Discovery via zeroconf."""

    def __init__(
        self,
        hass: HomeAssistant,
        zeroconf: HaZeroconf,
        zeroconf_types: dict[str, list[ZeroconfMatcher]],
        homekit_model_lookups: dict[str, HomeKitDiscoveredIntegration],
        homekit_model_matchers: dict[re.Pattern, HomeKitDiscoveredIntegration],
    ) -> None:
        """Init discovery."""
        self.hass = hass
        self.zeroconf = zeroconf
        self.zeroconf_types = zeroconf_types
        self.homekit_model_lookups = homekit_model_lookups
        self.homekit_model_matchers = homekit_model_matchers
        self.async_service_browser: AsyncServiceBrowser | None = None

    async def async_setup(self) -> None:
        """Start discovery."""
        types = list(self.zeroconf_types)
        # We want to make sure we know about other HomeAssistant
        # instances as soon as possible to avoid name conflicts
        # so we always browse for ZEROCONF_TYPE
        types.extend(
            hk_type
            for hk_type in (ZEROCONF_TYPE, *HOMEKIT_TYPES)
            if hk_type not in self.zeroconf_types
        )
        _LOGGER.debug("Starting Zeroconf browser for: %s", types)
        self.async_service_browser = AsyncServiceBrowser(
            self.zeroconf, types, handlers=[self.async_service_update]
        )

        async_dispatcher_connect(
            self.hass,
            config_entries.signal_discovered_config_entry_removed(DOMAIN),
            self._handle_config_entry_removed,
        )

    async def async_stop(self) -> None:
        """Cancel the service browser and stop processing the queue."""
        if self.async_service_browser:
            await self.async_service_browser.async_cancel()

    @callback
    def _handle_config_entry_removed(
        self,
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Handle config entry changes."""
        for discovery_key in entry.discovery_keys[DOMAIN]:
            if discovery_key.version != 1:
                continue
            _type = discovery_key.key[0]
            name = discovery_key.key[1]
            _LOGGER.debug("Rediscover service %s.%s", _type, name)
            self._async_service_update(self.zeroconf, _type, name)

    def _async_dismiss_discoveries(self, name: str) -> None:
        """Dismiss all discoveries for the given name."""
        for flow in self.hass.config_entries.flow.async_progress_by_init_data_type(
            ZeroconfServiceInfo,
            lambda service_info: bool(service_info.name == name),
        ):
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

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

        if state_change is ServiceStateChange.Removed:
            self._async_dismiss_discoveries(name)
            return

        self._async_service_update(zeroconf, service_type, name)

    @callback
    def _async_service_update(
        self,
        zeroconf: HaZeroconf,
        service_type: str,
        name: str,
    ) -> None:
        """Service state added or changed."""
        try:
            async_service_info = AsyncServiceInfo(service_type, name)
        except BadTypeInNameException as ex:
            # Some devices broadcast a name that is not a valid DNS name
            # This is a bug in the device firmware and we should ignore it
            _LOGGER.debug("Bad name in zeroconf record: %s: %s", name, ex)
            return

        if async_service_info.load_from_cache(zeroconf):
            self._async_process_service_update(async_service_info, service_type, name)
        else:
            self.hass.async_create_background_task(
                self._async_lookup_and_process_service_update(
                    zeroconf, async_service_info, service_type, name
                ),
                name=f"zeroconf lookup {name}.{service_type}",
            )

    async def _async_lookup_and_process_service_update(
        self,
        zeroconf: HaZeroconf,
        async_service_info: AsyncServiceInfo,
        service_type: str,
        name: str,
    ) -> None:
        """Update and process a zeroconf update."""
        await async_service_info.async_request(zeroconf, 3000)
        self._async_process_service_update(async_service_info, service_type, name)

    @callback
    def _async_process_service_update(
        self, async_service_info: AsyncServiceInfo, service_type: str, name: str
    ) -> None:
        """Process a zeroconf update."""
        info = info_from_service(async_service_info)
        if not info:
            # Prevent the browser thread from collapsing
            _LOGGER.debug("Failed to get addresses for device %s", name)
            return
        _LOGGER.debug("Discovered new device %s %s", name, info)
        props: dict[str, str | None] = info.properties
        discovery_key = DiscoveryKey(
            domain=DOMAIN,
            key=(info.type, info.name),
            version=1,
        )
        domain = None

        # If we can handle it as a HomeKit discovery, we do that here.
        if service_type in HOMEKIT_TYPES and (
            homekit_discovery := async_get_homekit_discovery(
                self.homekit_model_lookups, self.homekit_model_matchers, props
            )
        ):
            domain = homekit_discovery.domain
            discovery_flow.async_create_flow(
                self.hass,
                homekit_discovery.domain,
                {"source": config_entries.SOURCE_HOMEKIT},
                info,
                discovery_key=discovery_key,
            )
            # Continue on here as homekit_controller
            # still needs to get updates on devices
            # so it can see when the 'c#' field is updated.
            #
            # We only send updates to homekit_controller
            # if the device is already paired in order to avoid
            # offering a second discovery for the same device
            if not is_homekit_paired(props) and not homekit_discovery.always_discover:
                # If the device is paired with HomeKit we must send on
                # the update to homekit_controller so it can see when
                # the 'c#' field is updated. This is used to detect
                # when the device has been reset or updated.
                #
                # If the device is not paired and we should not always
                # discover it, we can stop here.
                return

        if not (matchers := self.zeroconf_types.get(service_type)):
            return

        # Not all homekit types are currently used for discovery
        # so not all service type exist in zeroconf_types
        for matcher in matchers:
            if len(matcher) > 1:
                if ATTR_NAME in matcher and not _memorized_fnmatch(
                    info.name.lower(), matcher[ATTR_NAME]
                ):
                    continue
                if ATTR_PROPERTIES in matcher and not _match_against_props(
                    matcher[ATTR_PROPERTIES], props
                ):
                    continue

            matcher_domain = matcher[ATTR_DOMAIN]
            # Create a type annotated regular dict since this is a hot path and creating
            # a regular dict is slightly cheaper than calling ConfigFlowContext
            context: config_entries.ConfigFlowContext = {
                "source": config_entries.SOURCE_ZEROCONF,
            }
            if domain:
                # Domain of integration that offers alternative API to handle
                # this device.
                context["alternative_domain"] = domain

            discovery_flow.async_create_flow(
                self.hass,
                matcher_domain,
                context,
                info,
                discovery_key=discovery_key,
            )


def async_get_homekit_discovery(
    homekit_model_lookups: dict[str, HomeKitDiscoveredIntegration],
    homekit_model_matchers: dict[re.Pattern, HomeKitDiscoveredIntegration],
    props: dict[str, Any],
) -> HomeKitDiscoveredIntegration | None:
    """Handle a HomeKit discovery.

    Return the domain to forward the discovery data to
    """
    if not (
        model := props.get(HOMEKIT_MODEL_LOWER) or props.get(HOMEKIT_MODEL_UPPER)
    ) or not isinstance(model, str):
        return None

    for split_str in _HOMEKIT_MODEL_SPLITS:
        key = (model.split(split_str))[0] if split_str else model
        if discovery := homekit_model_lookups.get(key):
            return discovery

    for pattern, discovery in homekit_model_matchers.items():
        if pattern.match(model):
            return discovery

    return None


def info_from_service(service: AsyncServiceInfo) -> ZeroconfServiceInfo | None:
    """Return prepared info from mDNS entries."""
    # See https://ietf.org/rfc/rfc6763.html#section-6.4 and
    # https://ietf.org/rfc/rfc6763.html#section-6.5 for expected encodings
    # for property keys and values
    if not (maybe_ip_addresses := service.ip_addresses_by_version(IPVersion.All)):
        return None
    if TYPE_CHECKING:
        ip_addresses = cast(list[IPv4Address | IPv6Address], maybe_ip_addresses)
    else:
        ip_addresses = maybe_ip_addresses
    ip_address: IPv4Address | IPv6Address | None = None
    for ip_addr in ip_addresses:
        if not ip_addr.is_link_local and not ip_addr.is_unspecified:
            ip_address = ip_addr
            break
    if not ip_address:
        return None

    if TYPE_CHECKING:
        assert (
            service.server is not None
        ), "server cannot be none if there are addresses"
    return ZeroconfServiceInfo(
        ip_address=ip_address,
        ip_addresses=ip_addresses,
        port=service.port,
        hostname=service.server,
        type=service.type,
        name=service.name,
        properties=service.decoded_properties,
    )


def _suppress_invalid_properties(properties: dict) -> None:
    """Suppress any properties that will cause zeroconf to fail to startup."""

    for prop, prop_value in properties.items():
        if not isinstance(prop_value, str):
            continue

        if len(prop_value.encode("utf-8")) > MAX_PROPERTY_VALUE_LEN:
            _LOGGER.error(
                (
                    "The property '%s' was suppressed because it is longer than the"
                    " maximum length of %d bytes: %s"
                ),
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
        (
            "The location name was truncated because it is longer than the maximum"
            " length of %d bytes: %s"
        ),
        MAX_NAME_LEN,
        location_name,
    )
    return location_name.encode("utf-8")[:MAX_NAME_LEN].decode("utf-8", "ignore")


@lru_cache(maxsize=4096, typed=True)
def _compile_fnmatch(pattern: str) -> re.Pattern:
    """Compile a fnmatch pattern."""
    return re.compile(translate(pattern))


@lru_cache(maxsize=1024, typed=True)
def _memorized_fnmatch(name: str, pattern: str) -> bool:
    """Memorized version of fnmatch that has a larger lru_cache.

    The default version of fnmatch only has a lru_cache of 256 entries.
    With many devices we quickly reach that limit and end up compiling
    the same pattern over and over again.

    Zeroconf has its own memorized fnmatch with its own lru_cache
    since the data is going to be relatively the same
    since the devices will not change frequently
    """
    return bool(_compile_fnmatch(pattern).match(name))
