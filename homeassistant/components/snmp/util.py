"""Support for displaying collected data over SNMP."""

from __future__ import annotations

from pysnmp.entity import config
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
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
]


async def async_create_request_cmd_args(
    hass: HomeAssistant,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
) -> RequestArgsType:
    """Create request arguments."""
    return await hass.async_add_executor_job(
        _create_request_cmd_args, auth_data, target
    )


def _create_request_cmd_args(
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
) -> RequestArgsType:
    """Create request arguments."""
    engine = SnmpEngine()
    context_data = ContextData()
    # Configure the auth data since it may do blocking
    # I/O to load the MIBs from disk
    if isinstance(auth_data, CommunityData):
        config.addV1System(
            engine,
            auth_data.communityIndex,
            auth_data.communityName,
            auth_data.contextEngineId,
            auth_data.contextName,
            auth_data.tag,
            auth_data.securityName,
        )
    elif isinstance(auth_data, UsmUserData):
        config.addV3User(
            engine,
            auth_data.userName,
            auth_data.authProtocol,
            auth_data.authKey,
            auth_data.privProtocol,
            auth_data.privKey,
            securityEngineId=auth_data.securityEngineId,
            securityName=auth_data.securityName,
            authKeyType=auth_data.authKeyType,
            privKeyType=auth_data.privKeyType,
        )
    return (engine, auth_data, target, context_data)
