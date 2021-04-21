"""Support for exposing Home Assistant via Zeroconf."""
from __future__ import annotations

from contextlib import suppress
import fnmatch
from functools import partial
import ipaddress
from ipaddress import ip_address
import logging
import socket
from typing import Any, Iterable, TypedDict, cast

from pyroute2 import IPRoute
import voluptuous as vol
from zeroconf import (
    Error as ZeroconfError,
    InterfaceChoice,
    IPVersion,
    NonUniqueNameException,
    ServiceInfo,
    ServiceStateChange,
    Zeroconf,
)

from homeassistant import util
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    __version__,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.singleton import singleton
from homeassistant.loader import async_get_homekit, async_get_zeroconf
from homeassistant.util.network import is_loopback

from .models import HaServiceBrowser, HaZeroconf
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
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    CONF_DEFAULT_INTERFACE, default=DEFAULT_DEFAULT_INTERFACE
                ): cv.boolean,
                vol.Optional(CONF_IPV6, default=DEFAULT_IPV6): cv.boolean,
            }
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


@singleton(DOMAIN)
async def async_get_instance(hass: HomeAssistant) -> HaZeroconf:
    """Zeroconf instance to be shared with other integrations that use it."""
    return await _async_get_instance(hass)


async def _async_get_instance(hass: HomeAssistant, **zcargs: Any) -> HaZeroconf:
    logging.getLogger("zeroconf").setLevel(logging.NOTSET)

    zeroconf = await hass.async_add_executor_job(partial(HaZeroconf, **zcargs))

    install_multiple_zeroconf_catcher(zeroconf)

    def _stop_zeroconf(_event: Event) -> None:
        """Stop Zeroconf."""
        zeroconf.ha_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_zeroconf)

    return zeroconf


def _get_ip_route(ip: str) -> Any:
    """Get ip next hop."""
    return IPRoute().route("get", dst=ip)


def _first_ip_nexthop_from_route(routes: Iterable) -> None | str:
    """Find the first RTA_PREFSRC in the routes."""
    _LOGGER.debug("Routes: %s", routes)
    for route in routes:
        for attr in route["attrs"]:
            if "RTA_PREFSRC" in attr:
                return cast(str, attr["RTA_PREFSRC"])
    return None


async def async_detect_interfaces_setting(hass: HomeAssistant) -> InterfaceChoice:
    """Auto detect the interfaces setting when unset."""
    routes = []
    try:
        routes = await hass.async_add_executor_job(_get_ip_route, MDNS_TARGET_IP)
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.debug(
            "The system could not auto detect routing data on your operating system; Zeroconf will broadcast on all interfaces",
            exc_info=ex,
        )
        return InterfaceChoice.All

    if not (first_ip := _first_ip_nexthop_from_route(routes)):
        _LOGGER.debug(
            "The system could not auto detect the nexthop for %s on your operating system; Zeroconf will broadcast on all interfaces",
            MDNS_TARGET_IP,
        )
        return InterfaceChoice.All

    if is_loopback(ip_address(first_ip)):
        _LOGGER.debug(
            "The next hop for %s is %s; Zeroconf will broadcast on all interfaces",
            MDNS_TARGET_IP,
            first_ip,
        )
        return InterfaceChoice.All

    return InterfaceChoice.Default


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Zeroconf and make Home Assistant discoverable."""
    zc_config = config.get(DOMAIN, {})
    zc_args: dict = {}

    if CONF_DEFAULT_INTERFACE not in zc_config:
        zc_args["interfaces"] = await async_detect_interfaces_setting(hass)
    elif zc_config[CONF_DEFAULT_INTERFACE]:
        zc_args["interfaces"] = InterfaceChoice.Default
    if not zc_config.get(CONF_IPV6, DEFAULT_IPV6):
        zc_args["ip_version"] = IPVersion.V4Only

    zeroconf = hass.data[DOMAIN] = await _async_get_instance(hass, **zc_args)

    async def _async_zeroconf_hass_start(_event: Event) -> None:
        """Expose Home Assistant on zeroconf when it starts.

        Wait till started or otherwise HTTP is not up and running.
        """
        uuid = await hass.helpers.instance_id.async_get()
        await hass.async_add_executor_job(
            _register_hass_zc_service, hass, zeroconf, uuid
        )

    async def _async_zeroconf_hass_started(_event: Event) -> None:
        """Start the service browser."""

        await _async_start_zeroconf_browser(hass, zeroconf)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_zeroconf_hass_start)
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED, _async_zeroconf_hass_started
    )

    return True


def _register_hass_zc_service(
    hass: HomeAssistant, zeroconf: HaZeroconf, uuid: str
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

    host_ip = util.get_local_ip()

    try:
        host_ip_pton = socket.inet_pton(socket.AF_INET, host_ip)
    except OSError:
        host_ip_pton = socket.inet_pton(socket.AF_INET6, host_ip)

    _suppress_invalid_properties(params)

    info = ServiceInfo(
        ZEROCONF_TYPE,
        name=f"{valid_location_name}.{ZEROCONF_TYPE}",
        server=f"{uuid}.local.",
        addresses=[host_ip_pton],
        port=hass.http.server_port,
        properties=params,
    )

    _LOGGER.info("Starting Zeroconf broadcast")
    try:
        zeroconf.register_service(info)
    except NonUniqueNameException:
        _LOGGER.error(
            "Home Assistant instance with identical name present in the local network"
        )


async def _async_start_zeroconf_browser(
    hass: HomeAssistant, zeroconf: HaZeroconf
) -> None:
    """Start the zeroconf browser."""

    zeroconf_types = await async_get_zeroconf(hass)
    homekit_models = await async_get_homekit(hass)

    types = list(zeroconf_types)

    for hk_type in HOMEKIT_TYPES:
        if hk_type not in zeroconf_types:
            types.append(hk_type)

    def service_update(
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Service state changed."""
        nonlocal zeroconf_types
        nonlocal homekit_models

        if state_change == ServiceStateChange.Removed:
            return

        _LOGGER.debug(
            "Service change - updated: service_type=%s name=%s state_changed=%s",
            service_type,
            name,
            state_change,
        )

        try:
            service_info = zeroconf.get_service_info(service_type, name)
        except ZeroconfError:
            _LOGGER.exception("Failed to get info for device %s", name)
            return

        if not service_info:
            # Prevent the browser thread from collapsing as
            # service_info can be None
            _LOGGER.debug("Failed to get info for device %s", name)
            return

        info = info_from_service(service_info)
        if not info:
            # Prevent the browser thread from collapsing
            _LOGGER.debug("Failed to get addresses for device %s", name)
            return

        _LOGGER.debug("Discovered new device %s %s", name, info)

        # If we can handle it as a HomeKit discovery, we do that here.
        if service_type in HOMEKIT_TYPES:
            discovery_was_forwarded = handle_homekit(hass, homekit_models, info)
            # Continue on here as homekit_controller
            # still needs to get updates on devices
            # so it can see when the 'c#' field is updated.
            #
            # We only send updates to homekit_controller
            # if the device is already paired in order to avoid
            # offering a second discovery for the same device
            if (
                discovery_was_forwarded
                and HOMEKIT_PAIRED_STATUS_FLAG in info["properties"]
            ):
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
        for entry in zeroconf_types.get(service_type, []):
            if len(entry) > 1:
                if (
                    uppercase_mac is not None
                    and "macaddress" in entry
                    and not fnmatch.fnmatch(uppercase_mac, entry["macaddress"])
                ):
                    continue
                if (
                    lowercase_name is not None
                    and "name" in entry
                    and not fnmatch.fnmatch(lowercase_name, entry["name"])
                ):
                    continue
                if (
                    lowercase_manufacturer is not None
                    and "manufacturer" in entry
                    and not fnmatch.fnmatch(
                        lowercase_manufacturer, entry["manufacturer"]
                    )
                ):
                    continue

            hass.add_job(
                hass.config_entries.flow.async_init(
                    entry["domain"], context={"source": DOMAIN}, data=info
                )  # type: ignore
            )

    _LOGGER.debug("Starting Zeroconf browser")
    HaServiceBrowser(zeroconf, types, handlers=[service_update])


def handle_homekit(
    hass: HomeAssistant, homekit_models: dict[str, str], info: HaServiceInfo
) -> bool:
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
        return False

    for test_model in homekit_models:
        if (
            model != test_model
            and not model.startswith(f"{test_model} ")
            and not model.startswith(f"{test_model}-")
        ):
            continue

        hass.add_job(
            hass.config_entries.flow.async_init(
                homekit_models[test_model], context={"source": "homekit"}, data=info
            )  # type: ignore
        )
        return True

    return False


def info_from_service(service: ServiceInfo) -> HaServiceInfo | None:
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
