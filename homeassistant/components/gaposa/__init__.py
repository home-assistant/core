"""The Gaposa integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN, UPDATE_INTERVAL  # noqa: F401
from .coordinator import DataUpdateCoordinatorGaposa

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gaposa from a config entry."""

    api_key = entry.data[CONF_API_KEY]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    coordinator = DataUpdateCoordinatorGaposa(
        hass,
        _LOGGER,
        api_key=api_key,
        username=username,
        password=password,
        name=entry.title,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Store runtime data that should persist between restarts
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Initialize runtime data with coordinator reference
    entry.runtime_data = {"coordinator": coordinator}

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Call async_setup_entry for each of the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Add any code needed to handle configuration updates


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: DataUpdateCoordinatorGaposa = entry.runtime_data["coordinator"]
        if coordinator.gaposa is not None:
            await coordinator.gaposa.close()

    return unload_ok
