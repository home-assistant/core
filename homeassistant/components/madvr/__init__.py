"""The madvr-envy integration."""

from __future__ import annotations

import logging

from madvr.madvr import Madvr

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import MadVRCoordinator
from .utils import cancel_tasks

PLATFORMS: list[Platform] = [Platform.REMOTE]

type MadVRConfigEntry = ConfigEntry[MadVRCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: MadVRConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    name = entry.data[CONF_NAME]
    madVRClient = Madvr(
        host=entry.data[CONF_HOST],
        logger=_LOGGER,
        port=entry.data[CONF_PORT],
        mac=entry.data[CONF_MAC],
        connect_timeout=10,
    )
    coordinator = MadVRCoordinator(
        hass,
        madVRClient,
        name=name,
    )
    hass.data.setdefault(DOMAIN, {})
    await coordinator.async_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN]["entry_id"] = entry.entry_id

    await coordinator.async_config_entry_first_refresh()

    # Forward the entry setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.add_update_listener(async_reload_entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MadVRConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MadVRCoordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            await cancel_tasks(coordinator.client)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: MadVRConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
