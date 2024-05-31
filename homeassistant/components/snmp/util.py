"""Support for displaying collected data over SNMP."""

from __future__ import annotations

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
from homeassistant.helpers.singleton import singleton

DATA_SNMP_ENGINE = "snmp_engine"

type RequestArgsType = tuple[
    SnmpEngine,
    UsmUserData | CommunityData,
    UdpTransportTarget | Udp6TransportTarget,
    ContextData,
    ObjectType,
]


async def async_create_request_cmd_args(
    hass: HomeAssistant,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
    object_id: str,
) -> RequestArgsType:
    """Create request arguments."""
    return (
        await async_get_snmp_engine(hass),
        auth_data,
        target,
        ContextData(),
        ObjectType(ObjectIdentity(object_id)),
    )


@singleton(DATA_SNMP_ENGINE)
async def async_get_snmp_engine(hass: HomeAssistant) -> SnmpEngine:
    """Get the SNMP engine."""
    return await hass.async_add_executor_job(_get_snmp_engine)


def _get_snmp_engine() -> SnmpEngine:
    """Return a cached instance of SnmpEngine."""
    engine = SnmpEngine()
    mib_controller = vbProcessor.getMibViewController(engine)
    # Actually load the MIBs from disk so we do
    # not do it in the event loop
    mib_controller.indexMib()
    builder: MibBuilder = mib_controller.mibBuilder
    if "PYSNMP-MIB" not in builder.mibSymbols:
        builder.loadModules()
    return engine
