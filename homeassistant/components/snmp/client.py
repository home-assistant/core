"""Client which talks to an SNMP device."""

from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
    bulk_walk_cmd,
    is_end_of_mib,
)
from pysnmp.smi.error import WrongValueError

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    CONF_CONTEXT_NAME,
    CONF_VERSION,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
)
from .util import async_create_transport_target, async_get_snmp_engine, create_auth_data

# Number of varbinds requested per bulk walk request
MAX_REPETITIONS = 50


class SnmpWalkError(Exception):
    """Error while walking part of the MIB."""


@dataclass
class SnmpClient:
    """Client for a single SNMP device.

    The engine, credentials, transport and context are shared by all subentries
    of a config entry, while each subentry reads its own part of the MIB.
    """

    engine: SnmpEngine
    auth_data: UsmUserData | CommunityData
    target: UdpTransportTarget | Udp6TransportTarget
    context_data: ContextData

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, data: Mapping[str, Any]
    ) -> SnmpClient:
        """Create a client for the device described by the entry data."""
        host = data[CONF_HOST]
        port = data.get(CONF_PORT, DEFAULT_PORT)
        context_name = data.get(CONF_CONTEXT_NAME)

        try:
            auth_data = create_auth_data(data, data.get(CONF_VERSION, DEFAULT_VERSION))
        except WrongValueError as err:
            raise ConfigEntryAuthFailed(
                f"Invalid authentication credentials or protocols: {err}"
            ) from err

        return cls(
            engine=await async_get_snmp_engine(hass),
            auth_data=auth_data,
            target=await async_create_transport_target(host, port, DEFAULT_TIMEOUT),
            context_data=(
                ContextData(contextName=context_name.encode())
                if context_name
                else ContextData()
            ),
        )

    async def async_walk(self, baseoid: str) -> AsyncGenerator[tuple[Any, Any]]:
        """Walk the subtree of baseoid, yielding the values it contains."""
        walker = bulk_walk_cmd(
            self.engine,
            self.auth_data,
            self.target,
            self.context_data,
            0,
            MAX_REPETITIONS,
            ObjectType(ObjectIdentity(baseoid)),
            lexicographicMode=False,
        )
        async for errindication, errstatus, errindex, res in walker:
            if errindication:
                message = f"SNMPLIB error: {errindication}"
                if isinstance(errindication, BaseException):
                    raise SnmpWalkError(message) from errindication
                raise SnmpWalkError(message)
            if errstatus:
                # The error index is 1 based and may point outside the response
                index = int(errindex) - 1 if errindex else -1
                oid = res[index][0] if 0 <= index < len(res) else "?"
                raise SnmpWalkError(f"SNMP error: {errstatus.prettyPrint()} at {oid}")
            if is_end_of_mib(res):
                break
            for varbind in res:
                yield varbind
