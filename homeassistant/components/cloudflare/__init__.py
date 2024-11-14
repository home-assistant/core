"""Update the IP addresses of your Cloudflare DNS records."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import socket

import pycfdns

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.location import async_detect_location_info
from homeassistant.util.network import is_ipv4_address, is_ipv6_address

from .const import CONF_RECORDS, DEFAULT_UPDATE_INTERVAL, DOMAIN, SERVICE_UPDATE_RECORDS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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

    async def update_records(now):
        """Set up recurring update."""
        try:
            await _async_update_cloudflare(
                hass, client, dns_zone, entry.data[CONF_RECORDS]
            )
        except (
            pycfdns.AuthenticationException,
            pycfdns.ComunicationException,
        ) as error:
            _LOGGER.error("Error updating zone %s: %s", entry.data[CONF_ZONE], error)

    async def update_records_service(call: ServiceCall) -> None:
        """Set up service for manual trigger."""
        try:
            await _async_update_cloudflare(
                hass, client, dns_zone, entry.data[CONF_RECORDS]
            )
        except (
            pycfdns.AuthenticationException,
            pycfdns.ComunicationException,
        ) as error:
            _LOGGER.error("Error updating zone %s: %s", entry.data[CONF_ZONE], error)

    update_interval = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
    entry.async_on_unload(
        async_track_time_interval(hass, update_records, update_interval)
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORDS, update_records_service)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Cloudflare config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True


async def _async_update_cloudflare(
    hass: HomeAssistant,
    client: pycfdns.Client,
    dns_zone: pycfdns.ZoneModel,
    target_records: list[str],
) -> None:
    _LOGGER.debug("Starting update for zone %s", dns_zone["name"])

    old_records = await client.list_dns_records(zone_id=dns_zone["id"])
    _LOGGER.debug("Records: %s", old_records)

    session = async_get_clientsession(hass, family=socket.AF_INET)
    session_ipv6 = async_get_clientsession(hass, family=socket.AF_INET6)

    location_info = await async_detect_location_info(session)
    location_info_v6 = await async_detect_location_info(session_ipv6)

    records_to_be_updated = []

    if location_info and is_ipv4_address(location_info.ip):
        _LOGGER.debug("IPv4 address detected: %s", location_info.ip)
        for record in old_records:
            if (
                record["name"] in target_records
                and record["content"] != location_info.ip
                and record["type"] == "A"
            ):
                _LOGGER.info(
                    "IPv4 address change detected for record: %s,will DNS entry from %s to %s",
                    record["name"],
                    record["content"],
                    location_info.ip,
                )
                record["content"] = location_info.ip
                records_to_be_updated.append(record)

    if location_info_v6 and is_ipv6_address(location_info_v6.ip):
        _LOGGER.debug("IPv6 address detected: %s", location_info_v6.ip)
        for record in old_records:
            if (
                record["name"] in target_records
                and record["content"] != location_info_v6.ip
                and record["type"] == "AAAA"
            ):
                _LOGGER.info(
                    "IPv6 address change detected for record: %s,will DNS entry from %s to %s",
                    record["name"],
                    record["content"],
                    location_info_v6.ip,
                )
                record["content"] = location_info_v6.ip
                records_to_be_updated.append(record)

    if len(records_to_be_updated) == 0:
        _LOGGER.debug("All target records are up to date")
        return

    await asyncio.gather(
        *[
            client.update_dns_record(
                zone_id=dns_zone["id"],
                record_id=record["id"],
                record_content=record["content"],
                record_name=record["name"],
                record_type=record["type"],
                record_proxied=record["proxied"],
            )
            for record in records_to_be_updated
        ]
    )

    _LOGGER.debug("Update for zone %s is complete", dns_zone["name"])
