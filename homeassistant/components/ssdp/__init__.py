"""The SSDP integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import partial
from typing import Any

from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo as _SsdpServiceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_ssdp, bind_hass
from homeassistant.util.logging import catch_log_exception

from . import websocket_api
from .const import DOMAIN, SSDP_SCANNER, UPNP_SERVER
from .scanner import (
    IntegrationMatchers,
    Scanner,
    SsdpChange,
    SsdpHassJobCallback,  # noqa: F401
)
from .server import Server

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

# Attributes for accessing info added by Home Assistant
ATTR_HA_MATCHING_DOMAINS = "x_homeassistant_matching_domains"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


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
    websocket_api.async_setup(hass)

    return True
