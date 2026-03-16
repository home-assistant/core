"""DataUpdateCoordinator for the SNMP integration."""

from __future__ import annotations

import binascii
import logging

from pysnmp.hlapi.v3arch.asyncio import bulk_walk_cmd, is_end_of_mib

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL
from .util import RequestArgsType

_LOGGER = logging.getLogger(__name__)


class SnmpUpdateCoordinator(DataUpdateCoordinator[list[str]]):
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

    async def _async_update_data(self) -> list[str]:
        """Fetch the current list of MAC addresses via an SNMP Walk."""
        devices = []
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
        async for errindication, errstatus, errindex, res in walker:
            if errindication:
                raise UpdateFailed(f"SNMPLIB error: {errindication}") from errindication
            if errstatus:
                err_msg = f"SNMP error: {errstatus.prettyPrint()} at {(errindex and res[int(errindex) - 1][0]) or '?'}"
                raise UpdateFailed(err_msg)

            for _oid, value in res:
                if not is_end_of_mib(res):
                    try:
                        mac = binascii.hexlify(value.asOctets()).decode("utf-8")
                    except AttributeError:
                        continue
                    mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
                    devices.append(mac)

        return devices
