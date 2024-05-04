"""Support for NuHeat thermostats."""

from datetime import timedelta
from http import HTTPStatus
import logging

import nuheat
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SERIAL_NUMBER, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


def _get_thermostat(api, serial_number):
    """Authenticate and create the thermostat object."""
    api.authenticate()
    return api.get_thermostat(serial_number)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NuHeat from a config entry."""

    conf = entry.data

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    serial_number = conf[CONF_SERIAL_NUMBER]

    api = nuheat.NuHeat(username, password)

    try:
        thermostat = await hass.async_add_executor_job(
            _get_thermostat, api, serial_number
        )
    except requests.exceptions.Timeout as ex:
        raise ConfigEntryNotReady from ex
    except requests.exceptions.HTTPError as ex:
        if (
            ex.response.status_code > HTTPStatus.BAD_REQUEST
            and ex.response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR
        ):
            _LOGGER.error("Failed to login to nuheat: %s", ex)
            return False
        raise ConfigEntryNotReady from ex
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Failed to login to nuheat: %s", ex)
        return False

    async def _async_update_data():
        """Fetch data from API endpoint."""
        await hass.async_add_executor_job(thermostat.get_data)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"nuheat {serial_number}",
        update_method=_async_update_data,
        update_interval=timedelta(minutes=5),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = (thermostat, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
