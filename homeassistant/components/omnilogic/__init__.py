"""The Omnilogic integration."""

import logging

from omnilogic import LoginException, OmniLogic, OmniLogicException

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import OmniLogicConfigEntry, OmniLogicUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hayward Omnilogic integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OmniLogicConfigEntry) -> bool:
    """Set up Omnilogic from a config entry."""

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    session = aiohttp_client.async_get_clientsession(hass)

    api = OmniLogic(username, password, session)

    try:
        await api.connect()
        await api.get_telemetry_data()
    except LoginException as error:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="login_failed",
        ) from error
    except OmniLogicException as error:
        _LOGGER.debug("OmniLogic API error: %s", error)
        raise ConfigEntryNotReady from error

    coordinator = OmniLogicUpdateCoordinator(
        hass=hass,
        api=api,
        name="Omnilogic",
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OmniLogicConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
