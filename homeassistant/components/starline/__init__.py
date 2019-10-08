"""The StarLine component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .account import StarlineAccount
from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_UPDATE_STATE,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured StarLine."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the StarLine device from a config entry."""
    account = StarlineAccount(hass, config_entry)
    await account.api.update()
    if not account.api.available:
        raise ConfigEntryNotReady

    hass.data[DOMAIN] = account

    device_registry = await hass.helpers.device_registry.async_get_registry()
    for device in account.api.devices.values():
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id, **account.device_info(device)
        )

    for domain in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, domain)
        )

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_STATE, account.api.update)

    config_entry.add_update_listener(async_options_updated)
    await async_options_updated(hass, config_entry)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for domain in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, domain)

    account: StarlineAccount = hass.data[DOMAIN]
    account.unload()
    return True


async def async_options_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Triggered by config entry options updates."""
    account: StarlineAccount = hass.data[DOMAIN]
    update_timeout = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    account.set_update_interval(hass, update_timeout)
