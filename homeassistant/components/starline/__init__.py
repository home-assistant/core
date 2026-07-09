"""The StarLine component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .account import StarlineAccount
from .const import (
    CONF_SCAN_OBD_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_OBD_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .services import async_setup_services

type StarlineConfigEntry = ConfigEntry[StarlineAccount]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the StarLine integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StarlineConfigEntry) -> bool:
    """Set up the StarLine device from a config entry."""
    account = StarlineAccount(hass, entry)
    await account.update()
    await account.update_obd()
    if not account.api.available:
        raise ConfigEntryNotReady

    entry.runtime_data = account

    device_registry = dr.async_get(hass)
    for device in account.api.devices.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **account.device_info(device)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    await async_options_updated(hass, entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: StarlineConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    config_entry.runtime_data.unload()
    return unload_ok


async def async_options_updated(
    hass: HomeAssistant, config_entry: StarlineConfigEntry
) -> None:
    """Triggered by config entry options updates."""
    account = config_entry.runtime_data
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_obd_interval = config_entry.options.get(
        CONF_SCAN_OBD_INTERVAL, DEFAULT_SCAN_OBD_INTERVAL
    )
    account.set_update_interval(scan_interval)
    account.set_update_obd_interval(scan_obd_interval)
