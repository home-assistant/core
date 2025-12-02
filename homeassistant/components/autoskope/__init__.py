"""The Autoskope integration."""

from __future__ import annotations

import logging

from autoskope_client.api import AutoskopeApi
from autoskope_client.models import CannotConnect, InvalidAuth
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DEFAULT_HOST
from .coordinator import AutoskopeConfigEntry, AutoskopeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: AutoskopeConfigEntry) -> bool:
    """Set up Autoskope from a config entry."""
    # Create API instance without session (will use internal session)
    api = AutoskopeApi(
        host=entry.data.get(CONF_HOST, DEFAULT_HOST),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        # Connect and authenticate with internal session
        await api.connect()
    except InvalidAuth as err:
        # Raise ConfigEntryError until reauth flow is implemented (then ConfigEntryAuthFailed)
        _LOGGER.error(
            "Authentication failed for Autoskope entry %s",
            entry.entry_id,
        )
        raise ConfigEntryError(
            "Authentication failed, please check credentials"
        ) from err
    except CannotConnect as err:
        _LOGGER.warning("Could not connect to Autoskope API")
        raise ConfigEntryNotReady("Could not connect to Autoskope API") from err

    coordinator = AutoskopeDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutoskopeConfigEntry) -> bool:
    """Unload a config entry."""
    # Clean up session before unloading platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.api.close()
    return unload_ok
