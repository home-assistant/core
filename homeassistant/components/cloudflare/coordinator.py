"""Contains the Coordinator for updating the IP addresses of your Cloudflare DNS records."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from logging import getLogger
import socket

import pycfdns

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.location import async_detect_location_info
from homeassistant.util.network import is_ipv4_address

from .const import CONF_RECORDS, DEFAULT_UPDATE_INTERVAL

_LOGGER = getLogger(__name__)

type CloudflareConfigEntry = ConfigEntry[CloudflareCoordinator]


class CloudflareCoordinator(DataUpdateCoordinator[None]):
    """Coordinates records updates."""

    config_entry: CloudflareConfigEntry
    client: pycfdns.Client
    zone: pycfdns.ZoneModel

    def __init__(
        self, hass: HomeAssistant, config_entry: CloudflareConfigEntry
    ) -> None:
        """Initialize an coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        self.client = pycfdns.Client(
            api_token=self.config_entry.data[CONF_API_TOKEN],
            client_session=async_get_clientsession(self.hass),
        )

        try:
            self.zone = next(
                zone
                for zone in await self.client.list_zones()
                if zone["name"] == self.config_entry.data[CONF_ZONE]
            )
        except pycfdns.AuthenticationException as e:
            raise ConfigEntryAuthFailed from e
        except pycfdns.ComunicationException as e:
            raise UpdateFailed("Error communicating with API") from e

    async def _async_update_data(self) -> None:
        """Update records."""
        _LOGGER.debug("Starting update for zone %s", self.zone["name"])
        try:
            records = await self.client.list_dns_records(
                zone_id=self.zone["id"], type="A"
            )
            _LOGGER.debug("Records: %s", records)

            target_records: list[str] = self.config_entry.data[CONF_RECORDS]

            location_info = await async_detect_location_info(
                async_get_clientsession(self.hass, family=socket.AF_INET)
            )

            if not location_info or not is_ipv4_address(location_info.ip):
                raise UpdateFailed("Could not get external IPv4 address")

            filtered_records = [
                record
                for record in records
                if record["name"] in target_records
                and record["content"] != location_info.ip
            ]

            if len(filtered_records) == 0:
                _LOGGER.debug("All target records are up to date")
                return

            await asyncio.gather(
                *[
                    self.client.update_dns_record(
                        zone_id=self.zone["id"],
                        record_id=record["id"],
                        record_content=location_info.ip,
                        record_name=record["name"],
                        record_type=record["type"],
                        record_proxied=record["proxied"],
                    )
                    for record in filtered_records
                ]
            )

            _LOGGER.debug("Update for zone %s is complete", self.zone["name"])

        except (
            pycfdns.AuthenticationException,
            pycfdns.ComunicationException,
        ) as e:
            raise UpdateFailed(
                f"Error updating zone {self.config_entry.data[CONF_ZONE]}"
            ) from e
