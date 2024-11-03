"""Support for displaying collected data over SNMP."""

from __future__ import annotations

import logging

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
)
from pysnmp.hlapi.v3arch.asyncio.cmdgen import LCD
from pysnmp.hlapi.varbinds import MibViewControllerManager

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

DATA_SNMP_ENGINE = "snmp_engine"

_LOGGER = logging.getLogger(__name__)

type CommandArgsType = tuple[
    SnmpEngine,
    UsmUserData | CommunityData,
    UdpTransportTarget | Udp6TransportTarget,
    ContextData,
]


type RequestArgsType = tuple[
    SnmpEngine,
    UsmUserData | CommunityData,
    UdpTransportTarget | Udp6TransportTarget,
    ContextData,
    ObjectType,
]


async def async_create_command_cmd_args(
    hass: HomeAssistant,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
) -> CommandArgsType:
    """Create command arguments.

    The ObjectType needs to be created dynamically by the caller.
    """
    engine = await async_get_snmp_engine(hass)
    return (engine, auth_data, target, ContextData())


async def async_create_request_cmd_args(
    hass: HomeAssistant,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
    object_id: str,
) -> RequestArgsType:
    """Create request arguments.

    The same ObjectType is used for all requests.
    """
    engine, auth_data, target, context_data = await async_create_command_cmd_args(
        hass, auth_data, target
    )
    object_type = ObjectType(ObjectIdentity(object_id))
    return (engine, auth_data, target, context_data, object_type)


@singleton(DATA_SNMP_ENGINE)
async def async_get_snmp_engine(hass: HomeAssistant) -> SnmpEngine:
    """Get the SNMP engine."""
    engine = await hass.async_add_executor_job(_get_snmp_engine)

    @callback
    def _async_shutdown_listener(ev: Event) -> None:
        _LOGGER.debug("Unconfiguring SNMP engine")
        LCD.unconfigure(engine, None)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_shutdown_listener)
    return engine


def _get_snmp_engine() -> SnmpEngine:
    """Return a cached instance of SnmpEngine."""
    engine = SnmpEngine()
    # Actually load the MIBs from disk so we do not do it in the event loop
    mib_view_controller = MibViewControllerManager.get_mib_view_controller(engine.cache)
    if "PYSNMP-MIB" not in mib_view_controller.mibBuilder.mibSymbols:
        mib_view_controller.mibBuilder.load_modules()
    engine.cache["mibViewController"] = mib_view_controller
    return engine
