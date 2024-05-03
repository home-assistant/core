"""The file component."""

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PLATFORM, CONF_VALUE_TEMPLATE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the file integration.

    The file integration uses config flow for configuration.
    But, a `file:` entry in configuration.yaml will trigger an import flow
    if a config entry doesn't already exist.
    """

    config_data: dict[str, list[ConfigType]] = {
        domain: [item for item in config[domain] if item.pop(CONF_PLATFORM) == DOMAIN]
        for domain in config
        if domain in PLATFORMS
    }
    # Ensure we pass the string value for a value_template
    if Platform.SENSOR in config_data and (
        items := [
            item for item in config_data[Platform.SENSOR] if CONF_VALUE_TEMPLATE in item
        ]
    ):
        for item in items:
            value_template: Template = item[CONF_VALUE_TEMPLATE]
            item[CONF_VALUE_TEMPLATE] = value_template.template
    if not hass.config_entries.async_entries(DOMAIN):
        # No config entry exists and configuration.yaml
        # config exists, then trigger the import flow.
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config_data,
            )
        )

    # The legacy File notify.notify service is deprecated with HA Core 2024.5.0
    # with HA Core 2024.5.0 and will be removed with HA core 2024.12.0
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            None,
            config,
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a file component entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
