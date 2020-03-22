"""Support for Nexia / Trane XL Thermostats."""
import asyncio
from datetime import timedelta
from functools import partial
import logging

from nexia.home import NexiaHome
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DATA_NEXIA, DOMAIN, NEXIA_DEVICE, PLATFORMS, UPDATE_COORDINATOR

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

DEFAULT_UPDATE_RATE = 120


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the nexia component from YAML."""

    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configure the base Nexia device for Home Assistant."""

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    try:
        nexia_home = await hass.async_add_executor_job(
            partial(
                NexiaHome,
                username=username,
                password=password,
                device_name=hass.config.location_name,
            )
        )
    except ConnectTimeout as ex:
        _LOGGER.error("Unable to connect to Nexia service: %s", ex)
        raise ConfigEntryNotReady
    except HTTPError as http_ex:
        if http_ex.response.status_code >= 400 and http_ex.response.status_code < 500:
            _LOGGER.error(
                "Access error from Nexia service, please check credentials: %s",
                http_ex,
            )
            return False
        _LOGGER.error("HTTP error from Nexia service: %s", http_ex)
        raise ConfigEntryNotReady

    async def _async_update_data():
        """Fetch data from API endpoint."""
        return await hass.async_add_job(nexia_home.update)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Nexia update",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=DEFAULT_UPDATE_RATE),
    )

    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id][DATA_NEXIA] = {
        NEXIA_DEVICE: nexia_home,
        UPDATE_COORDINATOR: coordinator,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
