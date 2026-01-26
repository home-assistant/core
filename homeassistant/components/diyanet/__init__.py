"""The Diyanet integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import DiyanetApiClient
from .const import CONF_LOCATION_ID, DOMAIN
from .coordinator import DiyanetCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type DiyanetConfigEntry = ConfigEntry[DiyanetCoordinator]

# This integration is configured via UI only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Diyanet domain and register services."""

    _LOGGER = logging.getLogger(__name__)

    async def _async_handle_refresh(call: ServiceCall) -> ServiceResponse:
        """Handle manual refresh of prayer times."""
        entry_id: str | None = call.data.get(ATTR_CONFIG_ENTRY_ID)

        if entry_id is not None:
            if not (entry := hass.config_entries.async_get_entry(entry_id)):
                raise ServiceValidationError("Entry not found")
            if entry.domain != DOMAIN:
                raise ServiceValidationError("Entry is not a Diyanet entry")
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError("Entry not loaded")

            coordinator: DiyanetCoordinator = entry.runtime_data
            _LOGGER.info("Manual refresh requested for config entry %s", entry_id)
            await coordinator.async_force_refresh()
            _LOGGER.debug("Manual refresh completed for config entry %s", entry_id)
            return None

        # No entry_id provided: refresh all loaded Diyanet entries
        loaded_entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]
        _LOGGER.info(
            "Manual refresh requested for all loaded entries (%d)", len(loaded_entries)
        )
        for entry in loaded_entries:
            coordinator = entry.runtime_data
            await coordinator.async_force_refresh()
        return None

    hass.services.async_register(
        DOMAIN,
        "refresh",
        _async_handle_refresh,
        schema=vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: DiyanetConfigEntry) -> bool:
    """Set up Diyanet from a config entry."""

    # Get credentials from config entry
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    location_id = entry.data[CONF_LOCATION_ID]

    # Create API client
    session = async_get_clientsession(hass)
    client = DiyanetApiClient(session, email, password)

    # Create coordinator
    coordinator = DiyanetCoordinator(hass, client, location_id, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Set up daily scheduled updates at 00:05
    await coordinator.async_setup()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DiyanetConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the coordinator's scheduled task
    entry.runtime_data.shutdown()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
