"""Initialize the Imeon component."""

from __future__ import annotations

import logging

from imeon_inverter_api.inverter import Inverter

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import InverterConfigEntry, InverterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: InverterConfigEntry) -> bool:
    """Handle the creation of a new config entry for the integration (asynchronous)."""
    websession = async_get_clientsession(hass)
    inverter = Inverter(entry.data[CONF_HOST], websession)

    # Create the corresponding HUB
    coordinator = InverterCoordinator(hass, entry, inverter)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Call for HUB creation then each entity as a List
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: InverterConfigEntry) -> bool:
    """Handle entry unloading."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
