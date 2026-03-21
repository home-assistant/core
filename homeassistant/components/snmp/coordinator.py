"""DataUpdateCoordinator for the SNMP integration."""

from __future__ import annotations

import binascii
import logging

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    ObjectIdentity,
    ObjectType,
    bulk_walk_cmd,
    get_cmd,
    is_end_of_mib,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL
from .util import RequestArgsType

_LOGGER = logging.getLogger(__name__)


class SnmpUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Class to manage fetching the list of MAC addresses from the router."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        request_args: RequestArgsType,
    ) -> None:
        """Initialize the manager."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.request_args = request_args
        self.manufacturer: str | None = None
        self.model: str | None = None
        self.sw_version: str | None = None
        self.sys_name: str | None = None

    async def _async_fetch_host_info(self) -> None:
        """Fetch host-specific info for the device registry."""
        engine, auth_data, target, context_data, _ = self.request_args

        # OID sysDescr.0 (1.3.6.1.2.1.1.1.0) and sysName.0 (1.3.6.1.2.1.1.5.0)
        try:
            get_result = await get_cmd(
                engine,
                auth_data,
                target,
                context_data,
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")),
                ObjectType(ObjectIdentity("1.3.6.1.2.1.1.5.0")),
            )
        except PySnmpError as err:
            _LOGGER.warning("Failed to fetch host info: %s", err)
            self.model = ""  # Prevent re-fetching
            return

        errindication, errstatus, _, restable = get_result

        if not errindication and not errstatus and len(restable) >= 2:
            descr = str(restable[0][1])
            self.sys_name = str(restable[1][1])

            # Try to extract manufacturer/model from sysDescr
            self.sw_version = descr
            if " " in descr:
                self.manufacturer, self.model = descr.split(" ", 1)
            else:
                self.model = descr

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the current list of MAC addresses via an SNMP Walk."""
        if self.model is None:
            await self._async_fetch_host_info()

        devices: dict[str, str] = {}
        engine, auth_data, target, context_data, object_type = self.request_args

        walker = bulk_walk_cmd(
            engine,
            auth_data,
            target,
            context_data,
            0,
            50,
            object_type,
            lexicographicMode=False,
        )
        try:
            async for errindication, errstatus, errindex, res in walker:
                if errindication:
                    raise UpdateFailed(
                        f"SNMPLIB error: {errindication}"
                    ) from errindication
                if errstatus:
                    err_msg = f"SNMP error: {errstatus.prettyPrint()} at {(errindex and res[int(errindex) - 1][0]) or '?'}"
                    raise UpdateFailed(err_msg)

                for oid, value in res:
                    if not is_end_of_mib(res):
                        try:
                            octets = value.asOctets()
                            if len(octets) == 6:
                                mac = binascii.hexlify(octets).decode("utf-8")
                            else:
                                mac = octets.decode("utf-8", "ignore")

                            # Normalize: remove non-hex chars, lowercase, and re-format
                            mac = "".join(c for c in mac if c.isalnum()).lower()
                            if len(mac) != 12:
                                continue
                            mac = ":".join([mac[i : i + 2] for i in range(0, 12, 2)])
                        except AttributeError, UnicodeDecodeError:
                            continue

                        # Extract IP address from OID suffix (last 4 parts)
                        ip = "0.0.0.0"
                        if hasattr(oid, "asTuple"):
                            oid_tuple = oid.asTuple()
                            if len(oid_tuple) >= 4:
                                ip = ".".join(map(str, oid_tuple[-4:]))
                        devices[mac] = ip
        except PySnmpError as err:
            raise UpdateFailed(f"SNMP error during walk: {err}") from err

        return devices
