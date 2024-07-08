"""The Telegram client integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SERVICE_SEND_MESSAGE
from .coordinator import TelegramClientCoordinator, TelegramClientEntryConfigEntry
from .schemas import SERVICE_SEND_MESSAGE_SCHEMA

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

SERVICE_SCHEMAS = {SERVICE_SEND_MESSAGE: SERVICE_SEND_MESSAGE_SCHEMA}

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
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_client_disconnect()

    return True
