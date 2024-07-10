"""The Telegram client integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import TelegramClientCoordinator, TelegramClientEntryConfigEntry

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Telegram client component."""

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
) -> bool:
    """Handle Telegram client entry setup."""
    coordinator = TelegramClientCoordinator(hass, entry)
    await coordinator.async_client_start()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(coordinator.resubscribe_listeners))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    coordinator: TelegramClientCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_client_disconnect()

    return True
