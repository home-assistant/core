"""The StarLine component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant

from .api import StarlineApi
from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_UPDATE_STATE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured StarLine."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the StarLine device from a config entry."""
    api = StarlineApi(
        hass, config_entry.data["user_id"], config_entry.data["slnet_token"]
    )
    await api.update()
    hass.data[DOMAIN] = api

    device_registry = await hass.helpers.device_registry.async_get_registry()
    for device_id, device in api.devices.items():
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id, **device.device_info
        )

    for domain in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, domain)
        )

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_STATE, api.update)

    config_entry.add_update_listener(async_options_updated)
    await async_options_updated(hass, config_entry)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for domain in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, domain)

    api: StarlineApi = hass.data[DOMAIN]
    api.unload()
    return True


async def async_options_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Triggered by config entry options updates."""
    api: StarlineApi = hass.data[DOMAIN]
    update_timeout = config_entry.options.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
    )
    api.set_update_interval(hass, update_timeout)
