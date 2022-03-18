"""Update the IP addresses of your Cloudflare DNS records."""
from __future__ import annotations

from datetime import timedelta
import logging

from pycfdns import CloudflareUpdater
from pycfdns.exceptions import (
    CloudflareAuthenticationException,
    CloudflareConnectionException,
    CloudflareException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_RECORDS, DEFAULT_UPDATE_INTERVAL, DOMAIN, SERVICE_UPDATE_RECORDS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cloudflare from a config entry."""
    cfupdate = CloudflareUpdater(
        async_get_clientsession(hass),
        entry.data[CONF_API_TOKEN],
        entry.data[CONF_ZONE],
        entry.data[CONF_RECORDS],
    )

    try:
        zone_id = await cfupdate.get_zone_id()
    except CloudflareAuthenticationException as error:
        raise ConfigEntryAuthFailed from error
    except CloudflareConnectionException as error:
        raise ConfigEntryNotReady from error

    async def update_records(now):
        """Set up recurring update."""
        try:
            await _async_update_cloudflare(cfupdate, zone_id)
        except CloudflareException as error:
            _LOGGER.error("Error updating zone %s: %s", entry.data[CONF_ZONE], error)

    async def update_records_service(call: ServiceCall) -> None:
        """Set up service for manual trigger."""
        try:
            await _async_update_cloudflare(cfupdate, zone_id)
        except CloudflareException as error:
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


async def _async_update_cloudflare(cfupdate: CloudflareUpdater, zone_id: str):
    _LOGGER.debug("Starting update for zone %s", cfupdate.zone)

    records = await cfupdate.get_record_info(zone_id)
    _LOGGER.debug("Records: %s", records)

    await cfupdate.update_records(zone_id, records)
    _LOGGER.debug("Update for zone %s is complete", cfupdate.zone)
