"""Integrate with Gandi Live DNS service."""
from datetime import timedelta
import logging

from gandi_api_livedns import GandiApiLiveDNS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_TTL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_FQDN,
    CONF_IPV6,
    CONF_RRNAME,
    CONF_RRTYPE,
    CONF_UPDATE_INTERVAL,
    DATA_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry."""

    minutes_update_interval = DEFAULT_UPDATE_INTERVAL
    if entry.options:
        minutes_update_interval = entry.options[CONF_UPDATE_INTERVAL]

    _LOGGER.debug(
        "Using api_key: %s for update record %s of %s.%s ttl: %s ipv6: %r interval: %s",
        entry.data[CONF_API_KEY],
        entry.data[CONF_RRTYPE],
        entry.data[CONF_RRNAME],
        entry.data[CONF_FQDN],
        entry.data[CONF_TTL],
        entry.data[CONF_IPV6],
        minutes_update_interval,
    )

    gandiApiLiveDNS = GandiApiLiveDNS(
        api_key=entry.data[CONF_API_KEY],
        domain=entry.data[CONF_FQDN],
        rrname=entry.data[CONF_RRNAME],
        rrtype=entry.data[CONF_RRTYPE],
        rrttl=entry.data[CONF_TTL],
        ipv6=entry.data[CONF_IPV6],
        logger=_LOGGER,
    )

    async def update_record(call):
        """Set up recurring update."""
        await _async_update_gandi_livedns(hass, gandiApiLiveDNS)

    update_interval = timedelta(minutes=minutes_update_interval)
    data_interval = async_track_time_interval(hass, update_record, update_interval)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_UPDATE_INTERVAL: data_interval,
    }

    hass.services.async_register(DOMAIN, "update_record", update_record)

    entry.add_update_listener(async_update_options)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    hass.data[DOMAIN][entry.entry_id][DATA_UPDATE_INTERVAL]()
    hass.data[DOMAIN].pop(entry.entry_id)

    return True


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def _async_update_gandi_livedns(
    hass: HomeAssistant, gandiApiLiveDNS: GandiApiLiveDNS
):
    _LOGGER.debug(
        "Starting update for %s.%s:%s",
        gandiApiLiveDNS.rrname,
        gandiApiLiveDNS.domain,
        gandiApiLiveDNS.rrtype,
    )
    await hass.async_add_executor_job(gandiApiLiveDNS.updateDNSRecord)
    _LOGGER.debug(
        "Update for %s.%s:%s is complete",
        gandiApiLiveDNS.rrname,
        gandiApiLiveDNS.domain,
        gandiApiLiveDNS.rrtype,
    )
