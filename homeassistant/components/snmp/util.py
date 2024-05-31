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
from pysnmp.hlapi.asyncio.cmdgen import vbProcessor
from pysnmp.smi.builder import MibBuilder

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
    mib_controller.indexMib()
    builder: MibBuilder = mib_controller.mibBuilder
    if "PYSNMP-MIB" not in builder.mibSymbols:
        builder.loadModules()
    object_identity.resolveWithMib(mib_controller)
    return (engine, auth_data, target, ContextData(), ObjectType(object_identity))
