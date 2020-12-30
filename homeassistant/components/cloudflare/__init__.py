"""Update the IP addresses of your Cloudflare DNS records."""
from datetime import timedelta
import logging
from typing import Dict

from pycfdns import CloudflareUpdater
from pycfdns.exceptions import (
    CloudflareAuthenticationException,
    CloudflareConnectionException,
    CloudflareException,
)
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_EMAIL, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_RECORDS,
    DATA_UNDO_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SERVICE_UPDATE_RECORDS,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_EMAIL),
            cv.deprecated(CONF_API_KEY),
            cv.deprecated(CONF_ZONE),
            cv.deprecated(CONF_RECORDS),
            vol.Schema(
                {
                    vol.Optional(CONF_EMAIL): cv.string,
                    vol.Optional(CONF_API_KEY): cv.string,
                    vol.Optional(CONF_ZONE): cv.string,
                    vol.Optional(CONF_RECORDS): vol.All(cv.ensure_list, [cv.string]),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the component."""
    hass.data.setdefault(DOMAIN, {})

    if len(hass.config_entries.async_entries(DOMAIN)) > 0:
        return True

    if DOMAIN in config and CONF_API_KEY in config[DOMAIN]:
        persistent_notification.async_create(
            hass,
            "Cloudflare integration now requires an API Token. Please go to the integrations page to setup.",
            "Cloudflare Setup",
            "cloudflare_setup",
        )

    return True


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
    except CloudflareAuthenticationException:
        _LOGGER.error("API access forbidden. Please reauthenticate")
        return False
    except CloudflareConnectionException as error:
        raise ConfigEntryNotReady from error

    async def update_records(now):
        """Set up recurring update."""
        try:
            await _async_update_cloudflare(cfupdate, zone_id)
        except CloudflareException as error:
            _LOGGER.error("Error updating zone %s: %s", entry.data[CONF_ZONE], error)

    async def update_records_service(call):
        """Set up service for manual trigger."""
        try:
            await _async_update_cloudflare(cfupdate, zone_id)
        except CloudflareException as error:
            _LOGGER.error("Error updating zone %s: %s", entry.data[CONF_ZONE], error)

    update_interval = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
    undo_interval = async_track_time_interval(hass, update_records, update_interval)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_UNDO_UPDATE_INTERVAL: undo_interval,
    }

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORDS, update_records_service)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Cloudflare config entry."""
    hass.data[DOMAIN][entry.entry_id][DATA_UNDO_UPDATE_INTERVAL]()
    hass.data[DOMAIN].pop(entry.entry_id)

    return True


async def _async_update_cloudflare(cfupdate: CloudflareUpdater, zone_id: str):
    _LOGGER.debug("Starting update for zone %s", cfupdate.zone)

    records = await cfupdate.get_record_info(zone_id)
    _LOGGER.debug("Records: %s", records)

    await cfupdate.update_records(zone_id, records)
    _LOGGER.debug("Update for zone %s is complete", cfupdate.zone)
