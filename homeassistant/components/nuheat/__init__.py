"""Support for NuHeat thermostats."""

from http import HTTPStatus
import logging

import nuheat
import requests

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SERIAL_NUMBER, PLATFORMS
from .coordinator import NuHeatConfigEntry, NuHeatCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_thermostat(api: nuheat.NuHeat, serial_number: str) -> nuheat.NuHeatThermostat:
    """Authenticate and create the thermostat object."""
    api.authenticate()
    return api.get_thermostat(serial_number)


async def async_setup_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> bool:
    """Set up NuHeat from a config entry."""

    conf = entry.data

    username: str = conf[CONF_USERNAME]
    password: str = conf[CONF_PASSWORD]
    serial_number: str = conf[CONF_SERIAL_NUMBER]

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
    except Exception as ex:  # noqa: BLE001
        _LOGGER.error("Failed to login to nuheat: %s", ex)
        return False

    entry.runtime_data = NuHeatCoordinator(hass, entry, thermostat)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NuHeatConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
