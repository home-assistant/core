"""The file component."""

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the file integration."""

    # The legacy File notify.notify service is deprecated with HA Core 2024.5.0
    # with HA Core 2024.5.0 and will be removed with HA core 2024.12.0
    # The legacy service will coexist together with the new entity platform service
    # hass.async_create_task(
    #    discovery.async_load_platform(
    #        hass,
    #        Platform.NOTIFY,
    #        DOMAIN,
    #        None,
    #        config,
    #    )
    # )

    if hass.config_entries.async_entries(DOMAIN):
        # We skip import in case we already have config entries
        return True

    # Prepare to import the YAML config into separate config entries
    config_data: dict[str, list[ConfigType]] = {
        domain: [item for item in config[domain] if item.pop(CONF_PLATFORM) == DOMAIN]
        for domain in config
        if domain in PLATFORMS
    }

    for domain, items in config_data.items():
        for item in items:
            item[CONF_PLATFORM] = domain
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data=item,
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a file component entry."""
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(entry.data[CONF_PLATFORM])]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [entry.data[CONF_PLATFORM]]
    )
