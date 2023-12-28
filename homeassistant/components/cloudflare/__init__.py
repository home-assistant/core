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
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.location import async_detect_location_info
from homeassistant.util.network import is_ipv4_address

from .const import CONF_RECORDS, DEFAULT_UPDATE_INTERVAL, DOMAIN, SERVICE_UPDATE_RECORDS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


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

    records = await client.list_dns_records(zone_id=dns_zone["id"], type="A")
    _LOGGER.debug("Records: %s", records)

    session = async_get_clientsession(hass, family=socket.AF_INET)
    location_info = await async_detect_location_info(session)

    if not location_info or not is_ipv4_address(location_info.ip):
        raise HomeAssistantError("Could not get external IPv4 address")

    filtered_records = [
        record
        for record in records
        if record["name"] in target_records and record["content"] != location_info.ip
    ]

    if len(filtered_records) == 0:
        _LOGGER.debug("All target records are up to date")
        return

    await asyncio.gather(
        *[
            client.update_dns_record(
                zone_id=dns_zone["id"],
                record_id=record["id"],
                record_content=location_info.ip,
                record_name=record["name"],
                record_type=record["type"],
                record_proxied=record["proxied"],
            )
            for record in filtered_records
        ]
    )

    _LOGGER.debug("Update for zone %s is complete", dns_zone["name"])
