"""The SSDP integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from functools import partial
from typing import Any

from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstant,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
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
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_ssdp, bind_hass
from homeassistant.util.logging import catch_log_exception

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

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_DEPRECATED_SsdpServiceInfo = DeprecatedConstant(
    _SsdpServiceInfo,
    "homeassistant.helpers.service_info.ssdp.SsdpServiceInfo",
    "2026.2",
)


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

    return True


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
