"""The met component."""
from homeassistant.core import Config, HomeAssistant
from .config_flow import MetFlowHandler  # noqa
from .const import DOMAIN, CONF_RADIUS  # noqa


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured Met."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Met as config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "weather")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "geo_location")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "weather")
    await hass.config_entries.async_forward_entry_unload(config_entry, "geo_location")
    return True


async def async_migrate_entry(hass, config_entry):
    """Migrate the config entry upon new versions."""
    if config_entry.version == 1:
        config_entry.data[CONF_RADIUS] = -1
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=config_entry.data)

    return True
