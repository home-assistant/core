"""Support for SleepIQ from SleepNumber."""
import logging
from datetime import timedelta

from asyncsleepiq import (
    AsyncSleepIQ,
    SleepIQAPIException,
    SleepIQLoginException,
    SleepIQTimeoutException,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
        }
    },
    extra=vol.ALLOW_EXTRA,
)


PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up sleepiq component."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the SleepIQ config entry."""
    conf = entry.data
    email = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    client_session = async_get_clientsession(hass)

    gateway = AsyncSleepIQ(client_session=client_session)

    try:
        await gateway.login(email, password)
    except SleepIQLoginException:
        _LOGGER.error("Could not authenticate with SleepIQ server")
        return False
    except SleepIQTimeoutException as err:
        raise ConfigEntryNotReady(
            str(err) or "Timed out during authentication"
        ) from err

    try:
        await gateway.init_beds()
    except SleepIQTimeoutException as err:
        raise ConfigEntryNotReady(
            str(err) or "Timed out during initialization"
        ) from err
    except SleepIQAPIException as err:
        raise ConfigEntryNotReady(str(err) or "Error reading from SleepIQ API") from err

    coordinator: DataUpdateCoordinator[None] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"SleepIQ Bed Statuses - {email}",
        update_method=gateway.fetch_bed_statuses,
        update_interval=UPDATE_INTERVAL,
    )

    # Call the SleepIQ API to refresh data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        SLEEPIQ_DATA: gateway,
        SLEEPIQ_STATUS_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
