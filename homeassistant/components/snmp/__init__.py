"""The snmp component."""

import logging

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    DOMAIN,
    SNMP_VERSIONS,
)
from .coordinator import SnmpUpdateCoordinator
from .util import async_create_request_cmd_args, async_get_snmp_engine

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

type SnmpConfigEntry = ConfigEntry[SnmpUpdateCoordinator]

__all__ = ["async_get_snmp_engine"]


async def async_setup_entry(hass: HomeAssistant, entry: SnmpConfigEntry) -> bool:
    """Set up SNMP from a config entry."""
    host = entry.data[CONF_HOST]
    community = entry.data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    baseoid = entry.data[CONF_BASEOID]
    authkey = entry.data.get(CONF_AUTH_KEY)
    privkey = entry.data.get(CONF_PRIV_KEY)

    authproto = DEFAULT_AUTH_PROTOCOL
    privproto = DEFAULT_PRIV_PROTOCOL

    if authkey is not None or privkey is not None:
        if not authkey:
            authproto = "none"
        if not privkey:
            privproto = "none"

        auth_data = UsmUserData(
            community,
            authKey=authkey or None,
            privKey=privkey or None,
            authProtocol=authproto,
            privProtocol=privproto,
        )
    else:
        auth_data = CommunityData(community, mpModel=SNMP_VERSIONS[DEFAULT_VERSION])

    try:
        target = await UdpTransportTarget.create(
            (host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
        )
    except PySnmpError:
        try:
            target = Udp6TransportTarget((host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT)
        except PySnmpError as err:
            _LOGGER.error("Invalid SNMP host: %s", err)
            return False

    request_args = await async_create_request_cmd_args(
        hass,
        auth_data,
        target,
        baseoid,
    )

    coordinator = SnmpUpdateCoordinator(hass, entry, request_args)
    await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=coordinator.manufacturer,
        model=coordinator.model,
        name=coordinator.sys_name or host,
        sw_version=coordinator.sw_version,
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This line shuts down the platforms we started in 'async_setup_entry'.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
