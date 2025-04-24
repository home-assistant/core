"""The Autoskope integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import AutoskopeDataUpdateCoordinator
from .models import (
    AutoskopeApi,
    AutoskopeConfigEntry,
    AutoskopeRuntimeData,
    CannotConnect,
    InvalidAuth,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Autoskope integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AutoskopeConfigEntry) -> bool:
    """Set up Autoskope from a config entry."""

    # Create API instance, passing hass for session management
    api = AutoskopeApi(
        host=entry.data.get(CONF_HOST, DEFAULT_HOST),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        hass=hass,
    )

    # Validate credentials before setting up coordinator
    try:
        authenticated = await api.authenticate()
        if not authenticated:
            _LOGGER.error("Authentication failed unexpectedly during setup")
            return False
    except InvalidAuth:
        _LOGGER.warning(
            "Authentication failed for Autoskope entry %s. Please re-authenticate",
            entry.entry_id,
        )
        return False  # Setup fails, user needs to re-auth via UI
    except CannotConnect as err:
        _LOGGER.warning("Could not connect to Autoskope API")
        raise ConfigEntryNotReady("Could not connect to Autoskope API") from err
    except Exception:
        _LOGGER.exception(
            "Unexpected error setting up Autoskope entry %s", entry.entry_id
        )
        return False

    # If authentication is successful, create the coordinator
    coordinator = AutoskopeDataUpdateCoordinator(hass, api=api, entry=entry)

    # Perform the first refresh before storing runtime data and setting up platforms
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator instance in runtime_data
    entry.runtime_data = AutoskopeRuntimeData(coordinator=coordinator)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutoskopeConfigEntry) -> bool:
    """Unload a config entry."""
    # Forward unload to platforms using runtime data if needed by platforms during unload
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
