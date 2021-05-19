"""The Network Configuration integration."""
from __future__ import annotations

import enum

from pyroute2 import IPRoute
import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass

DOMAIN = "network"

CONF_INTERFACES = "interfaces"
CONF_INTERFACE_LIST = "interface_list"

INTERFACE_AUTO = "auto"
INTERFACE_DEFAULT = "default"
INTERFACE_ALL = "all"
INTERFACE_MANUAL = "manual"


class Interface(enum.Enum):
    """Represent the inteface."""

    all = INTERFACE_ALL
    default = INTERFACE_DEFAULT
    manual = INTERFACE_MANUAL

    def __str__(self) -> str:  # pylint: disable=invalid-str-returned
        """Return the event."""
        return self.value


class HaInterfaceConfig(TypedDict):
    """Prepared info from mDNS entries."""

    interfaces: Interface
    interface_list: int | None


@bind_hass
async def async_get_interface_config(hass: HomeAssistant) -> HaZeroconf:
    """Zeroconf instance to be shared with other integrations that use it."""
    return cast(HaZeroconf, (await _async_get_instance(hass)).zeroconf)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up network for Home Assistant."""
    network_config = config.get(DOMAIN, {})


def _get_ip_route(dst_ip: str) -> Any:
    """Get ip next hop."""
    return IPRoute().route("get", dst=dst_ip)


def _first_ip_nexthop_from_route(routes: Iterable) -> None | str:
    """Find the first RTA_PREFSRC in the routes."""
    _LOGGER.debug("Routes: %s", routes)
    for route in routes:
        for key, value in route["attrs"]:
            if key == "RTA_PREFSRC":
                return cast(str, value)
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
