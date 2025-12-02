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


async def _get_ip(hass, needs_it, family, validator):
    if not needs_it:
        return None
    session = async_get_clientsession(hass, family=family)
    location_info = await async_detect_location_info(session)
    if not location_info:
        return None
    if not validator(location_info.ip):
        return None
    return location_info.ip


async def _async_update_cloudflare(
    hass: HomeAssistant,
    entry: CloudflareConfigEntry,
) -> None:
    client = entry.runtime_data.client
    dns_zone = entry.runtime_data.dns_zone
    target_records: list[str] = entry.data[CONF_RECORDS]

    _LOGGER.debug("Starting update for zone %s", dns_zone["name"])

    records = await client.list_dns_records(zone_id=dns_zone["id"])
    _LOGGER.debug("Records: %s", records)

    needs_ipv4 = any(record["type"] == "A" for record in records)
    needs_ipv6 = any(record["type"] == "AAAA" for record in records)
    ipv4, ipv6 = await asyncio.gather(
        _get_ip(hass, needs_ipv4, socket.AF_INET, is_ipv4_address),
        _get_ip(hass, needs_ipv6, socket.AF_INET6, is_ipv6_address),
    )

    def ipByFamily(family):
        if family == "A":
            if not ipv4:
                raise HomeAssistantError(
                    "Could not get external IPv4 address (remove A record to use IPv6 only)"
                )
            return ipv4
        if family == "AAAA":
            if not ipv6:
                raise HomeAssistantError(
                    "Could not get external IPv6 address (remove AAAA record to use IPv4 only)"
                )
            return ipv6
        raise AssertionError("Bad family")

    filtered_records = [
        record
        for record in records
        if record["type"] in ["A", "AAAA"]
        and record["name"] in target_records
        and record["content"] != ipByFamily(record["type"])
    ]

    if len(filtered_records) == 0:
        _LOGGER.debug("All target records are up to date")
        return

    await asyncio.gather(
        *[
            client.update_dns_record(
                zone_id=dns_zone["id"],
                record_id=record["id"],
                record_content=ipByFamily(record["type"]),
                record_name=record["name"],
                record_type=record["type"],
                record_proxied=record["proxied"],
            )
            for record in filtered_records
        ]
    )

    _LOGGER.debug("Update for zone %s is complete", dns_zone["name"])
