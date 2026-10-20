"""Data update coordinator for the Meraki integration."""

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, override

from meraki import APIError
from meraki.aio import AsyncDashboardAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import is_auth_error
from .const import CONF_ORGANIZATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=1)

# Clients seen in this window are returned, connected or not.
CLIENT_TIMESPAN = timedelta(hours=1)

# Networks with these products have clients; Bluetooth clients are seen by access
# points.
CLIENT_PRODUCT_TYPES = frozenset({"appliance", "cellularGateway", "switch", "wireless"})
BLUETOOTH_PRODUCT_TYPE = "wireless"

type MerakiConfigEntry = ConfigEntry[MerakiDataUpdateCoordinator]


@dataclass(frozen=True, kw_only=True)
class MerakiClient:
    """A Wi-Fi or wired client of a Meraki network."""

    mac: str
    network_id: str
    description: str | None
    ip: str | None
    online: bool
    last_seen: datetime


@dataclass(frozen=True, kw_only=True)
class MerakiBluetoothClient:
    """A Bluetooth device seen by Meraki access points."""

    mac: str
    network_id: str
    name: str | None
    last_seen: datetime


@dataclass(frozen=True, kw_only=True)
class MerakiData:
    """The clients of a Meraki organization, by MAC address."""

    clients: dict[str, MerakiClient]
    bluetooth_clients: dict[str, MerakiBluetoothClient]


class MerakiDataUpdateCoordinator(DataUpdateCoordinator[MerakiData]):
    """Poll the clients of a Meraki organization's networks."""

    config_entry: MerakiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MerakiConfigEntry,
        client: AsyncDashboardAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.organization_id: str = config_entry.data[CONF_ORGANIZATION_ID]

    @override
    async def _async_update_data(self) -> MerakiData:
        """Fetch the clients of all networks of the organization."""
        networks = await self._async_call(
            self.client.organizations.getOrganizationNetworks(
                self.organization_id, total_pages="all"
            )
        )
        client_networks = [
            network["id"]
            for network in networks
            if CLIENT_PRODUCT_TYPES.intersection(network["productTypes"])
        ]
        bluetooth_networks = [
            network["id"]
            for network in networks
            if BLUETOOTH_PRODUCT_TYPE in network["productTypes"]
        ]
        timespan = int(CLIENT_TIMESPAN.total_seconds())
        client_lists = await asyncio.gather(
            *(
                self._async_call(
                    self.client.networks.getNetworkClients(
                        network_id, total_pages="all", perPage=5000, timespan=timespan
                    )
                )
                for network_id in client_networks
            )
        )
        bluetooth_lists = await asyncio.gather(
            *(
                self._async_call(
                    self.client.networks.getNetworkBluetoothClients(
                        network_id, total_pages="all", perPage=1000, timespan=timespan
                    )
                )
                for network_id in bluetooth_networks
            )
        )

        clients: dict[str, MerakiClient] = {}
        for network_id, items in zip(client_networks, client_lists, strict=True):
            for item in items:
                client = _parse_client(network_id, item)
                # A client that moved between networks is listed in both.
                if (known := clients.get(client.mac)) is None or _is_more_recent(
                    client, known
                ):
                    clients[client.mac] = client

        bluetooth_clients: dict[str, MerakiBluetoothClient] = {}
        for network_id, items in zip(bluetooth_networks, bluetooth_lists, strict=True):
            for item in items:
                bluetooth_client = _parse_bluetooth_client(network_id, item)
                known_bt = bluetooth_clients.get(bluetooth_client.mac)
                if known_bt is None or bluetooth_client.last_seen > known_bt.last_seen:
                    bluetooth_clients[bluetooth_client.mac] = bluetooth_client

        return MerakiData(clients=clients, bluetooth_clients=bluetooth_clients)

    async def _async_call[_T](self, request: Awaitable[_T]) -> _T:
        """Await an API request and translate its errors."""
        try:
            return await request
        except APIError as err:
            if is_auth_error(err):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err


def _parse_client(network_id: str, item: dict[str, Any]) -> MerakiClient:
    return MerakiClient(
        mac=item["mac"],
        network_id=network_id,
        description=item["description"],
        ip=item["ip"],
        online=item["status"] == "Online",
        last_seen=dt_util.parse_datetime(item["lastSeen"], raise_on_error=True),
    )


def _parse_bluetooth_client(
    network_id: str, item: dict[str, Any]
) -> MerakiBluetoothClient:
    # Devices that do not advertise a name are reported as "unknown".
    name = item["name"] or item["deviceName"]
    return MerakiBluetoothClient(
        mac=item["mac"],
        network_id=network_id,
        name=name if name and name != "unknown" else None,
        # Unlike the other endpoints, lastSeen is a Unix timestamp here.
        last_seen=dt_util.utc_from_timestamp(item["lastSeen"]),
    )


def _is_more_recent(client: MerakiClient, other: MerakiClient) -> bool:
    """Return True if client is the more recent sighting of the same MAC."""
    return (client.online, client.last_seen) > (other.online, other.last_seen)
