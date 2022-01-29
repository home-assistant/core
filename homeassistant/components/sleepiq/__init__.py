"""Support for SleepIQ from SleepNumber."""
from datetime import timedelta
import asyncio
import logging

from asyncsleepiq import AsyncSleepIQ, SleepIQLoginException, SleepIQTimeoutException
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.BUTTON]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the SleepIQ component."""
    hass.data.setdefault(DOMAIN, {})
    conf = config.get(DOMAIN)
    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_EMAIL: conf[CONF_EMAIL],
                CONF_PASSWORD: conf[CONF_PASSWORD],
            },
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SleepIQ from a config entry."""

    entry_data = entry.data
    email = entry_data[CONF_EMAIL]
    password = entry_data[CONF_PASSWORD]

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
            str(err) or "Timed out during realtime update"
        ) from err

    status_coordinator: DataUpdateCoordinator[None] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"SleepIQ Bed Statuses - {email}",
        update_method=gateway.update_bed_statuses,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    # Start out as unavailable so we do not report 0 data
    # until the update happens
    status_coordinator.last_update_success = False
    asyncio.create_task(status_coordinator.async_request_refresh())

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        SLEEPIQ_DATA: gateway,
        SLEEPIQ_STATUS_COORDINATOR: status_coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
