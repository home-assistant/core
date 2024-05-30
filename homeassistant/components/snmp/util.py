"""Support for displaying collected data over SNMP."""

from __future__ import annotations

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
)
from pysnmp.hlapi.asyncio.cmdgen import lcd

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
    # Configure the LCD which does blocking I/O
    lcd.configure(engine, auth_data, target, context_data.contextName)
    return (engine, auth_data, target, context_data)
