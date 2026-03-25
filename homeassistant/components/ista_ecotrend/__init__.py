"""The ista Ecotrend integration."""

from __future__ import annotations

import logging

from pyecotrend_ista import PyEcotrendIsta

from homeassistant.components.recorder import get_instance
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import IstaConfigEntry, IstaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IstaConfigEntry) -> bool:
    """Set up ista EcoTrend from a config entry."""
    ista = PyEcotrendIsta(
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        _LOGGER,
    )

    coordinator = IstaCoordinator(hass, entry, ista)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IstaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: IstaConfigEntry) -> None:
    """Handle removal of an entry."""
    statistic_ids = [f"{DOMAIN}:{name}" for name in entry.options.values()]
    get_instance(hass).async_clear_statistics(statistic_ids)
