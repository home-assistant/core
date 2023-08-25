"""The Internet Printing Protocol (IPP) integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as dr_async_get

from .const import CONF_BASE_PATH, DOMAIN
from .coordinator import IPPDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IPP from a config entry."""
    # config flow sets this to either UUID, serial number or None
    if (device_id := entry.unique_id) is None:
        device_id = entry.entry_id

    coordinator = IPPDataUpdateCoordinator(
        hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        base_path=entry.data[CONF_BASE_PATH],
        tls=entry.data[CONF_SSL],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        device_id=device_id,
    )

    dev_reg = dr_async_get(hass)
    device_entry = dev_reg.async_get_device(
        identifiers={(DOMAIN, device_id)},
    )

    if device_entry and entry.entry_id not in device_entry.config_entries:
        device_entry = None

    if not device_entry:
        await coordinator.async_config_entry_first_refresh()
    else:
        await coordinator.async_refresh()

    if coordinator.last_update_success:
        coordinator.initialized = True
        device_entry = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device_id)},
            manufacturer=coordinator.data.info.manufacturer,
            model=coordinator.data.info.model,
            name=coordinator.data.info.name,
            sw_version=coordinator.data.info.version,
            configuration_url=coordinator.data.info.more_info,
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
