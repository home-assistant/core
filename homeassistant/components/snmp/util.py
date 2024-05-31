"""Support for displaying collected data over SNMP."""

from __future__ import annotations

from functools import cache

import pysnmp.hlapi.asyncio as hlapi
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
)
from pysnmp.hlapi.asyncio.cmdgen import vbProcessor

from homeassistant.core import HomeAssistant

from .const import MAP_AUTH_PROTOCOLS, MAP_PRIV_PROTOCOLS, SNMP_VERSIONS

type RequestArgsType = tuple[
    SnmpEngine,
    UsmUserData | CommunityData,
    UdpTransportTarget | Udp6TransportTarget,
    ContextData,
    ObjectType,
]


@cache
def snmp_engine() -> SnmpEngine:
    """Return a cached instance of SnmpEngine."""
    return SnmpEngine()


async def async_create_request_cmd_args(
    hass: HomeAssistant,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
    object_id: str,
) -> RequestArgsType:
    """Create request arguments."""
    return await hass.async_add_executor_job(
        _create_request_cmd_args, auth_data, target, object_id
    )


def _create_request_cmd_args(
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
    object_id: str,
) -> RequestArgsType:
    """Create request arguments."""
    engine = snmp_engine()
    object_identity = ObjectIdentity(object_id)
    mib_controller = vbProcessor.getMibViewController(engine)
    # Actually load the MIBs from disk so we do
    # not do it in the event loop
    object_identity.resolveWithMib(mib_controller)
    return (engine, auth_data, target, ContextData(), ObjectType(object_identity))


def make_auth_data(
    version: str,
    community: str | None,
    authproto: str | None,
    authkey: str | None,
    privproto: str | None,
    privkey: str | None,
    username: str | None,
) -> CommunityData | UsmUserData:
    """Create auth data."""
    if version != "3":
        return CommunityData(community, mpModel=SNMP_VERSIONS[version])
    if not authkey or not authproto:
        authproto = "none"
    if not privkey or not privproto:
        privproto = "none"
    return UsmUserData(
        username,
        authKey=authkey or None,
        privKey=privkey or None,
        authProtocol=getattr(hlapi, MAP_AUTH_PROTOCOLS[authproto]),
        privProtocol=getattr(hlapi, MAP_PRIV_PROTOCOLS[privproto]),
    )
