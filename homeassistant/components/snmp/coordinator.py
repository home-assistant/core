"""DataUpdateCoordinator for the SNMP integration."""

import binascii
from datetime import timedelta
import logging
from typing import override

from pysnmp.error import PySnmpError
from pysnmp.smi.error import WrongValueError

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import SnmpClient, SnmpWalkError
from .const import (
    CONF_BASEOID,
    CONF_INTERVAL_SECONDS,
    DEFAULT_INTERVAL_SECONDS,
    DOMAIN,
    IP_INDEXED_MAC_OIDS,
)

_LOGGER = logging.getLogger(__name__)

# A single lost packet must not mark all tracked devices as unavailable
MAX_CONSECUTIVE_FAILURES = 3


def normalize_mac(value: bytes) -> str | None:
    """Return the MAC address in the canonical colon separated format.

    Routers report MAC addresses either as raw bytes or as text in one of the
    usual formats, so both are accepted. Returns None if the value does not
    describe a 6 byte MAC address.
    """
    if len(value) == 6:
        mac = binascii.hexlify(value).decode("utf-8")
    else:
        mac = value.decode("utf-8", "ignore")

    mac = "".join(char for char in mac if char.isalnum()).lower()
    if len(mac) != 12 or not all(char in "0123456789abcdef" for char in mac):
        return None
    return ":".join(mac[i : i + 2] for i in range(0, 12, 2))


def _ip_address_from_oid(oid: tuple[int, ...]) -> str | None:
    """Return the IPv4 address of an OID, if its table is indexed by it.

    Only the MAC columns of IP-indexed tables pair a MAC address with an IPv4
    address in the row index. In tables indexed by the MAC the trailing
    components of the OID mean something else.
    """
    for prefix in IP_INDEXED_MAC_OIDS:
        # The row index is the interface index plus the four address octets
        if oid[: len(prefix)] != prefix or len(oid) != len(prefix) + 5:
            continue
        octets = oid[-4:]
        if any(not 0 <= octet <= 255 for octet in octets):
            return None
        return ".".join(map(str, octets))
    return None


class SnmpDeviceTrackerCoordinator(DataUpdateCoordinator[dict[str, str | None]]):
    """Class to fetch the MAC addresses of a device tracker subentry."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry,
        client: SnmpClient,
    ) -> None:
        """Initialize the coordinator."""
        interval = subentry.data.get(CONF_INTERVAL_SECONDS, DEFAULT_INTERVAL_SECONDS)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {subentry.title}",
            update_interval=timedelta(seconds=interval),
        )
        self.subentry_id = subentry.subentry_id
        self._baseoid: str = subentry.data[CONF_BASEOID]
        self._client = client
        self._consecutive_failures = 0

    @override
    async def _async_update_data(self) -> dict[str, str | None]:
        """Fetch the current list of MAC addresses via an SNMP Walk."""
        try:
            devices = await self._async_walk_table()
        except UpdateFailed as err:
            self._consecutive_failures += 1
            previous_data = self.data
            if (
                previous_data is None
                or self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES
            ):
                raise
            _LOGGER.warning(
                "Transient SNMP failure (%s/%s), keeping the previous data: %s",
                self._consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
                err,
            )
            return previous_data

        self._consecutive_failures = 0
        return devices

    async def _async_walk_table(self) -> dict[str, str | None]:
        """Walk the table of the subentry and return the MAC addresses it holds."""
        devices: dict[str, str | None] = {}

        try:
            async for oid, value in self._client.async_walk(self._baseoid):
                try:
                    octets = value.asOctets()
                except AttributeError, UnicodeDecodeError:
                    continue

                if (mac := normalize_mac(octets)) is None:
                    continue

                devices[mac] = _ip_address_from_oid(oid.asTuple())
        except WrongValueError as err:
            raise ConfigEntryAuthFailed(
                f"Invalid authentication credentials or protocols: {err}"
            ) from err
        except (PySnmpError, SnmpWalkError) as err:
            raise UpdateFailed(f"SNMP error during walk: {err}") from err

        return devices
