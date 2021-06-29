"""Integrate with Gandi Live DNS service."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DOMAIN,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_TTL,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_IPV6,
    CONF_UPDATE_INTERVAL,
    DATA_UPDATE_INTERVAL,
    DOMAIN,
    SERVICE_UPDATE_RECORDS,
)
from .gandi import GandiApiLiveDNS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entry."""

    try:
        gandiApiLiveDNS = GandiApiLiveDNS(
            hass,
            {
                CONF_DOMAIN: entry.data[CONF_DOMAIN],
                CONF_API_KEY: entry.data[CONF_API_KEY],
                CONF_NAME: entry.data[CONF_NAME],
                CONF_TYPE: entry.data[CONF_TYPE],
                CONF_TTL: entry.data[CONF_TTL],
                CONF_IPV6: entry.data[CONF_IPV6],
                CONF_TIMEOUT: entry.data[CONF_TIMEOUT],
            },
            _LOGGER,
        )
    except Exception as ex:
        _LOGGER.error(
            "An exception of type %s occurred. Arguments:\n{1!r}", type(ex).__name__
        )
        return False

    async def update_records(now):
        """Set up recurring update."""
        try:
            await _async_update_gandi_livedns(gandiApiLiveDNS)
        except Exception as ex:
            _LOGGER.error(
                "Error updating %s.%s:%s %s",
                entry.data[CONF_NAME],
                entry.data[CONF_DOMAIN],
                entry.data[CONF_TYPE],
                type(ex).__name__,
            )

    async def update_records_service(call):
        try:
            await _async_update_gandi_livedns(gandiApiLiveDNS)
        except Exception as ex:
            _LOGGER.error(
                "Error service updating %s.%s:%s %s",
                entry.data[CONF_NAME],
                entry.data[CONF_DOMAIN],
                entry.data[CONF_TYPE],
                type(ex).__name__,
            )

    update_interval = timedelta(minutes=entry.data[CONF_UPDATE_INTERVAL])
    data_interval = async_track_time_interval(hass, update_records, update_interval)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_UPDATE_INTERVAL: data_interval,
    }

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORDS, update_records_service)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    hass.data[DOMAIN][entry.entry_id][DATA_UPDATE_INTERVAL]()
    hass.data[DOMAIN].pop(entry.entry_id)

    return True


async def _async_update_gandi_livedns(gandiApiLiveDNS: GandiApiLiveDNS):
    _LOGGER.debug(
        "Starting update for %s.%s:%s",
        gandiApiLiveDNS.rrname,
        gandiApiLiveDNS.domain,
        gandiApiLiveDNS.rrtype,
    )
    await gandiApiLiveDNS.updateDNSRecord()
    _LOGGER.debug(
        "Update for %s.%s:%s is complete",
        gandiApiLiveDNS.rrname,
        gandiApiLiveDNS.domain,
        gandiApiLiveDNS.rrtype,
    )
