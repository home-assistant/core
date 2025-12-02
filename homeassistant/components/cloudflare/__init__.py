"""Update the IP addresses of your Cloudflare DNS records."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import socket

import pycfdns

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.location import async_detect_location_info
from homeassistant.util.network import is_ipv4_address, is_ipv6_address

from .const import CONF_RECORDS, DEFAULT_UPDATE_INTERVAL, DOMAIN, SERVICE_UPDATE_RECORDS

_LOGGER = logging.getLogger(__name__)

type CloudflareConfigEntry = ConfigEntry[CloudflareRuntimeData]


@dataclass
class CloudflareRuntimeData:
    """Runtime data for Cloudflare config entry."""

    client: pycfdns.Client
    dns_zone: pycfdns.ZoneModel


async def async_setup_entry(hass: HomeAssistant, entry: CloudflareConfigEntry) -> bool:
    """Set up Cloudflare from a config entry."""
    session = async_get_clientsession(hass)
    client = pycfdns.Client(
        api_token=entry.data[CONF_API_TOKEN],
        client_session=session,
    )

    try:
        dns_zones = await client.list_zones()
        dns_zone = next(
            zone for zone in dns_zones if zone["name"] == entry.data[CONF_ZONE]
        )
    except pycfdns.AuthenticationException as error:
        raise ConfigEntryAuthFailed from error
    except pycfdns.ComunicationException as error:
        raise ConfigEntryNotReady from error

    entry.runtime_data = CloudflareRuntimeData(client, dns_zone)

    async def update_records(now: datetime) -> None:
        """Set up recurring update."""
        try:
            await _async_update_cloudflare(hass, entry)
        except (
            pycfdns.AuthenticationException,
            pycfdns.ComunicationException,
        ) as error:
            _LOGGER.error("Error updating zone %s: %s", entry.data[CONF_ZONE], error)

    async def update_records_service(call: ServiceCall) -> None:
        """Set up service for manual trigger."""
        try:
            await _async_update_cloudflare(hass, entry)
        except (
            pycfdns.AuthenticationException,
            pycfdns.ComunicationException,
        ) as error:
            _LOGGER.error("Error updating zone %s: %s", entry.data[CONF_ZONE], error)

    update_interval = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
    entry.async_on_unload(
        async_track_time_interval(hass, update_records, update_interval)
    )

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORDS, update_records_service)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CloudflareConfigEntry) -> bool:
    """Unload Cloudflare config entry."""

    return True


async def _async_update_cloudflare(
    hass: HomeAssistant,
    entry: CloudflareConfigEntry,
) -> None:
    client = entry.runtime_data.client
    dns_zone = entry.runtime_data.dns_zone
    target_records: list[tuple[str, str]] = []
    # Handle legacy CONF_RECORDS, if there is just the record name
    if all("|" not in record for record in entry.data[CONF_RECORDS]):
        # Legacy: only record name, assume type "A"
        target_records = [(record, "A") for record in entry.data[CONF_RECORDS]]
    else:
        # New: list of "name|type" strings
        target_records = [
            tuple(record.split("|", 1)) for record in entry.data[CONF_RECORDS]
        ]

    _LOGGER.debug("Starting update for zone %s", dns_zone["name"])

    records_a = await client.list_dns_records(zone_id=dns_zone["id"], type="A")
    records_aaaa = await client.list_dns_records(zone_id=dns_zone["id"], type="AAAA")
    records = records_a + records_aaaa
    _LOGGER.debug("Records: %s", records)

    session = async_get_clientsession(hass, family=socket.AF_INET)
    session_ipv6 = async_get_clientsession(hass, family=socket.AF_INET6)
    location_info = await async_detect_location_info(session)
    location_info_ipv6 = await async_detect_location_info(session_ipv6)

    ipv4_address = location_info.ip if location_info else None
    ipv6_address = location_info_ipv6.ip if location_info_ipv6 else None

    if ipv4_address is not None and not is_ipv4_address(ipv4_address):
        _LOGGER.debug("Could not get IPv4 address ")
        ipv4_address = None

    if ipv6_address is not None and not is_ipv6_address(ipv6_address):
        _LOGGER.debug("Could not get IPv6 address ")
        ipv6_address = None

    if not ipv4_address and not ipv6_address:
        raise HomeAssistantError("Could not get any external IP address")

    update_tasks = []

    for record in records:
        if (record["name"], record["type"]) not in target_records:
            continue

        if record["type"] == "A" and ipv4_address and record["content"] != ipv4_address:
            update_tasks.append(
                client.update_dns_record(
                    zone_id=dns_zone["id"],
                    record_id=record["id"],
                    record_content=ipv4_address,
                    record_name=record["name"],
                    record_type="A",
                    record_proxied=record["proxied"],
                )
            )
            _LOGGER.debug(
                "Updating the content for the record %s (%s)", record["name"], record["type"]
            )

        elif (
            record["type"] == "AAAA"
            and ipv6_address
            and record["content"] != ipv6_address
        ):
            update_tasks.append(
                client.update_dns_record(
                    zone_id=dns_zone["id"],
                    record_id=record["id"],
                    record_content=ipv6_address,
                    record_name=record["name"],
                    record_type="AAAA",
                    record_proxied=record["proxied"],
                )
            )
            _LOGGER.debug(
                "Added Record %s (%s) to Updatetask", record["name"], record["type"]
            )

    if not update_tasks:
        _LOGGER.debug("All possible target records are up to date")
        return

    await asyncio.gather(*update_tasks)

    _LOGGER.debug("DNS record update for zone %s is complete", dns_zone["name"])
