"""Support for displaying collected data over SNMP."""

from __future__ import annotations

from functools import cache

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

from homeassistant.core import HomeAssistant

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
        _create_request_cmd_args, snmp_engine(), auth_data, target, object_id
    )


def _create_request_cmd_args(
    engine: SnmpEngine,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
    object_id: str,
) -> RequestArgsType:
    """Create request arguments."""
    context_data = ContextData()
    object_type = ObjectType(ObjectIdentity(object_id))
    return (engine, auth_data, target, context_data, object_type)
