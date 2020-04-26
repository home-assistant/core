"""The gogogate2 component."""
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .common import async_can_connect, get_api


async def async_setup(hass: HomeAssistant, base_config: dict) -> bool:
    """Set up for Gogogate2 controllers."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Do setup of Gogogate2."""
    # Update the config entry to use options values if it has them.
    config_data = config_entry.data
    hass.config_entries.async_update_entry(
        config_entry,
        title=config_entry.options.get(CONF_NAME, config_data[CONF_NAME]),
        data={
            CONF_NAME: config_entry.options.get(CONF_NAME, config_data[CONF_NAME]),
            CONF_IP_ADDRESS: config_entry.options.get(
                CONF_IP_ADDRESS, config_data[CONF_IP_ADDRESS]
            ),
            CONF_USERNAME: config_entry.options.get(
                CONF_USERNAME, config_data[CONF_USERNAME]
            ),
            CONF_PASSWORD: config_entry.options.get(
                CONF_PASSWORD, config_data[CONF_PASSWORD]
            ),
        },
    )

    config_entry.add_update_listener(async_options_updated)

    api = get_api(config_entry.data)
    if not await async_can_connect(hass, api):
        # Returning true so we can still unload the platform later.
        return True

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
    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(config_entry, COVER_DOMAIN)
    )
    return True
