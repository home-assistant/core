"""Support for displaying collected data over SNMP."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pysnmp.error import PySnmpError
import pysnmp.hlapi.v3arch.asyncio as hlapi
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
from pysnmp.smi import view

from homeassistant.const import CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import (
    CONF_AUTH_KEY,
    CONF_AUTH_PROTOCOL,
    CONF_COMMUNITY,
    CONF_PRIV_KEY,
    CONF_PRIV_PROTOCOL,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PRIV_PROTOCOL,
    MAP_AUTH_PROTOCOLS,
    MAP_PRIV_PROTOCOLS,
)

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


def create_auth_data(
    data: Mapping[str, Any], version: str
) -> UsmUserData | CommunityData:
    """Create SNMP auth data from config dict."""
    if version == "3":
        username: str = data[CONF_USERNAME]
        auth_key: str | None = data.get(CONF_AUTH_KEY)
        auth_proto: str = data.get(CONF_AUTH_PROTOCOL, DEFAULT_AUTH_PROTOCOL)
        priv_key: str | None = data.get(CONF_PRIV_KEY)
        priv_proto: str = data.get(CONF_PRIV_PROTOCOL, DEFAULT_PRIV_PROTOCOL)

        return UsmUserData(
            username,
            authKey=auth_key,
            authProtocol=getattr(hlapi, MAP_AUTH_PROTOCOLS[auth_proto]),
            privKey=priv_key,
            privProtocol=getattr(hlapi, MAP_PRIV_PROTOCOLS[priv_proto])
            if (data.get(CONF_PRIV_PROTOCOL) or priv_key)
            else getattr(hlapi, MAP_PRIV_PROTOCOLS["none"]),
        )

    community: str = data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    return CommunityData(community, mpModel=1 if version == "2c" else 0)


async def async_create_transport_target(
    host: str, port: int, timeout: float
) -> UdpTransportTarget | Udp6TransportTarget:
    """Create SNMP transport target with IPv4 / IPv6 fallback."""
    try:
        return await UdpTransportTarget.create((host, port), timeout=timeout)
    except PySnmpError:
        return await Udp6TransportTarget.create((host, port), timeout=timeout)


async def async_create_command_cmd_args(
    hass: HomeAssistant,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
    context_name: str | None = None,
) -> CommandArgsType:
    """Create command arguments.

    The ObjectType needs to be created dynamically by the caller.
    """
    engine = await async_get_snmp_engine(hass)
    context_data = (
        ContextData(contextName=context_name.encode())
        if context_name
        else ContextData()
    )
    return (engine, auth_data, target, context_data)


async def async_create_request_cmd_args(
    hass: HomeAssistant,
    auth_data: UsmUserData | CommunityData,
    target: UdpTransportTarget | Udp6TransportTarget,
    object_id: str,
    context_name: str | None = None,
) -> RequestArgsType:
    """Create request arguments.

    The same ObjectType is used for all requests.
    """
    engine, auth_data, target, context_data = await async_create_command_cmd_args(
        hass, auth_data, target, context_name
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
    mib_view_controller = view.MibViewController(
        engine.message_dispatcher.mib_instrum_controller.get_mib_builder()
    )
    engine.cache["mibViewController"] = mib_view_controller
    mib_view_controller.mibBuilder.load_modules()
    return engine
