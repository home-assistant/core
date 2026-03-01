"""Contains the Coordinator for updating the IP addresses of your Cloudflare DNS records."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import timedelta
from logging import getLogger
import socket
from typing import Any

import pycfdns

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.location import async_detect_location_info
from homeassistant.util.network import is_ipv4_address

from .const import CONF_DOMAINS, CONF_RECORDS, DEFAULT_UPDATE_INTERVAL
from .helpers import async_create_a_record

_LOGGER = getLogger(__name__)


@dataclass
class CloudflareRuntimeData:
    """Runtime data for Cloudflare config entry."""

    client: pycfdns.Client
    dns_zone: pycfdns.ZoneModel
    coordinator: DataUpdateCoordinator[dict[str, Any]]
    api_token: str


type CloudflareConfigEntry = ConfigEntry[CloudflareRuntimeData]


class CloudflareCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinates records updates."""

    config_entry: CloudflareConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: CloudflareConfigEntry,
        client: pycfdns.Client,
        zone: pycfdns.ZoneModel,
    ) -> None:
        """Initialize an coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"cloudflare-{zone['name']}",
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )
        self.client = client
        self.zone = zone

    async def _async_get_external_ipv4(self) -> str:
        loc_session = async_get_clientsession(self.hass, family=socket.AF_INET)
        location_info = await async_detect_location_info(loc_session)
        if not location_info or not is_ipv4_address(location_info.ip):
            raise UpdateFailed("Could not get external IPv4 address")
        return location_info.ip

    async def _async_update_data(self) -> dict[str, Any]:
        """Update records."""
        zone_id = self.zone["id"]
        external_ip = await self._async_get_external_ipv4()
        configured_domains: list[str] = (
            self.config_entry.data.get(CONF_DOMAINS)
            or self.config_entry.data.get(CONF_RECORDS)
            or []
        )

        try:
            # Retrieve existing A records for zone
            records = await self.client.list_dns_records(zone_id=zone_id, type="A")
        except pycfdns.AuthenticationException as error:
            raise ConfigEntryAuthFailed("Authentication failed") from error
        except pycfdns.ComunicationException as error:
            raise UpdateFailed("Communication error") from error

        record_index: dict[str, pycfdns.RecordModel] = {r["name"]: r for r in records}
        results: dict[str, Any] = {}

        tasks: list[Awaitable[Any]] = []
        task_domains: list[str] = []
        for domain in configured_domains:
            record = record_index.get(domain)
            if record is None:
                # Create missing record (proxied True by default)
                tasks.append(
                    async_create_a_record(
                        session=async_get_clientsession(self.hass),
                        api_token=self.config_entry.data[CONF_API_TOKEN],
                        zone_id=zone_id,
                        name=domain,
                        content=external_ip,
                        proxied=True,
                    )
                )
                task_domains.append(domain)
            elif record["content"] != external_ip:
                # Update IP while keeping proxied state
                tasks.append(
                    self.client.update_dns_record(
                        zone_id=zone_id,
                        record_id=record["id"],
                        record_content=external_ip,
                        record_name=record["name"],
                        record_type=record["type"],
                        record_proxied=record["proxied"],
                    )
                )
                task_domains.append(domain)
            results[domain] = record or None

        if tasks:
            update_results = await asyncio.gather(*tasks, return_exceptions=True)
            for domain, result in zip(task_domains, update_results, strict=True):
                if isinstance(result, Exception):
                    _LOGGER.error("Error updating %s: %s", domain, result)
                elif result is None:
                    _LOGGER.error(
                        "Error creating record for %s: Result was None", domain
                    )

            if any(
                isinstance(result, Exception) or result is None
                for result in update_results
            ):
                raise UpdateFailed("Error updating one or more Cloudflare records")

            # Refresh records after modifications
            try:
                records = await self.client.list_dns_records(zone_id=zone_id, type="A")
            except pycfdns.AuthenticationException as error:
                raise ConfigEntryAuthFailed("Authentication failed") from error
            except pycfdns.ComunicationException as error:
                # If we fail here, we still might have partial success, but the state will be possibly inconsistent
                # For now raising UpdateFailed seems appropriate
                raise UpdateFailed(f"Failed to refresh records: {error}") from error

        refreshed_index = {r["name"]: r for r in records}
        for domain in configured_domains:
            results[domain] = refreshed_index.get(domain)

        return {
            "external_ip": external_ip,
            "records": results,
            "updated_at": dt_util.utcnow(),
        }
