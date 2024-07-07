"""The Telegram client integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_DEVICE_ID, DOMAIN, SERVICE_SEND_MESSAGE
from .coordinator import TelegramClientCoordinator, TelegramClientEntryConfigEntry
from .schemas import SERVICE_SEND_MESSAGE_SCHEMA
from .services import async_telegram_call

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

SERVICE_SCHEMAS = {SERVICE_SEND_MESSAGE: SERVICE_SEND_MESSAGE_SCHEMA}

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Telegram client component."""

    async def _async_telegram_call(call: ServiceCall):
        device_id = call.data[ATTR_DEVICE_ID]
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if not device:
            return
        coordinator: TelegramClientCoordinator = hass.data[DOMAIN][
            device.primary_config_entry
        ]
        await async_telegram_call(coordinator, call)

    for service_name, service_schema in SERVICE_SCHEMAS.items():
        hass.services.async_register(
            DOMAIN,
            service_name,
            _async_telegram_call,
            schema=service_schema,
        )

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
    if entry.entry_id in hass.data[DOMAIN]:
        device = hass.data[DOMAIN][entry.entry_id]
        await device.async_disconnect()

    return True


async def async_remove_entry(
    hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
) -> None:
    """Handle removal of an entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        coordinator: TelegramClientCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_client_disconnect()
        del hass.data[DOMAIN][entry.entry_id]
