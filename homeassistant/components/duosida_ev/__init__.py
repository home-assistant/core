"""The Duosida EV Charger integration."""

from __future__ import annotations

import logging

from duosida_ev import DuosidaCharger

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_SWITCH_DEBOUNCE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SWITCH_DEBOUNCE,
)
from .coordinator import DuosidaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    # Future PRs will add:
    # Platform.BINARY_SENSOR,
    # Platform.BUTTON,
    # Platform.NUMBER,
    # Platform.SWITCH,
]

type DuosidaConfigEntry = ConfigEntry[DuosidaDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DuosidaConfigEntry) -> bool:
    """Set up Duosida EV Charger from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 9988)
    device_id = entry.data[CONF_DEVICE_ID]

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    switch_debounce = entry.options.get(
        CONF_SWITCH_DEBOUNCE,
        entry.data.get(CONF_SWITCH_DEBOUNCE, DEFAULT_SWITCH_DEBOUNCE),
    )

    _LOGGER.debug(
        "Setting up Duosida charger at %s:%s (device_id: %s)", host, port, device_id
    )

    charger = DuosidaCharger(
        host=host,
        port=port,
        device_id=device_id,
        debug=False,
    )

    coordinator = DuosidaDataUpdateCoordinator(
        hass,
        charger,
        scan_interval,
        device_id,
        switch_debounce,
    )

    await coordinator.async_load_stored_settings()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("Duosida charger at %s set up successfully", host)
    return True


async def async_update_options(hass: HomeAssistant, entry: DuosidaConfigEntry) -> None:
    """Update options."""
    _LOGGER.debug("Options updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DuosidaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry.runtime_data.disconnect()
        _LOGGER.info("Duosida charger unloaded successfully")

    return unload_ok
