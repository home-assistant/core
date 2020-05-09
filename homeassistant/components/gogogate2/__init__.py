"""The gogogate2 component."""
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .common import (
    async_api_info_or_none,
    create_data_manager,
    get_api,
    get_data_manager,
)


async def async_setup(hass: HomeAssistant, base_config: dict) -> bool:
    """Set up for Gogogate2 controllers."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Do setup of Gogogate2."""
    # Config entry is coming from config flow and needs options set.
    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry, data={}, options=config_entry.data,
        )

    config_entry.add_update_listener(async_options_updated)

    api = get_api(config_entry.options)
    if await async_api_info_or_none(hass, api) is None:
        raise ConfigEntryNotReady()

    data_manager = create_data_manager(hass, config_entry, api)
    data_manager.start_polling()

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, COVER_DOMAIN)
    )

    return True


async def async_options_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Options were updated."""
    config_entry.update_listeners = []
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Gogogate2 config entry."""
    data_manager = get_data_manager(hass, config_entry)
    data_manager.stop_polling()

    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(config_entry, COVER_DOMAIN)
    )

    return True
