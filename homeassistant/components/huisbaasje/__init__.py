"""The EnergyFlip integration."""

import logging

from energyflip import EnergyFlip, EnergyFlipException

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import FETCH_TIMEOUT, SOURCE_TYPES
from .coordinator import EnergyFlipConfigEntry, EnergyFlipUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: EnergyFlipConfigEntry) -> bool:
    """Set up EnergyFlip from a config entry."""
    # Create the EnergyFlip client
    energyflip = EnergyFlip(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        source_types=SOURCE_TYPES,
        request_timeout=FETCH_TIMEOUT,
    )

    # Attempt authentication. If this fails, an exception is thrown
    try:
        await energyflip.authenticate()
    except EnergyFlipException as exception:
        _LOGGER.error("Authentication failed: %s", str(exception))
        return False

    # Create a coordinator for polling updates
    coordinator = EnergyFlipUpdateCoordinator(hass, entry, energyflip)

    await coordinator.async_config_entry_first_refresh()

    # Load the client in the data of home assistant
    entry.runtime_data = coordinator

    # Offload the loading of entities to the platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnergyFlipConfigEntry) -> bool:
    """Unload a config entry."""
    # Forward the unloading of the entry to the platform
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
