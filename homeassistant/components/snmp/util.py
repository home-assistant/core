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
from pysnmp.hlapi.asyncio.transport import AbstractTransportTarget

from homeassistant.core import HomeAssistant

type RequestArgsType = tuple[
    SnmpEngine,
    UsmUserData | CommunityData,
    UdpTransportTarget | Udp6TransportTarget,
    ContextData,
]


class NullTransport(AbstractTransportTarget):
    """Null transport target."""

    def openClientMode(self) -> None:
        """Open client mode."""


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
    # Configure the LCD which does blocking I/O, but we cannot
    # configure the transport because it needs to be run in the
    # event loop so we use a null transport.
    lcd.configure(engine, auth_data, NullTransport(), context_data.contextName)
    return (engine, auth_data, target, context_data)
