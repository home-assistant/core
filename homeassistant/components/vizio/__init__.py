"""The vizio component."""
import asyncio

import voluptuous as vol

from homeassistant.components.media_player import DEVICE_CLASS_TV
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import CONF_APPS, CONF_DEVICE_CLASS, DOMAIN, VIZIO_SCHEMA


def validate_apps(config: ConfigType) -> ConfigType:
    """Validate CONF_APPS is only used when CONF_DEVICE_CLASS == DEVICE_CLASS_TV."""
    if (
        config.get(CONF_APPS) is not None
        and config[CONF_DEVICE_CLASS] != DEVICE_CLASS_TV
    ):
        raise vol.Invalid(
            f"'{CONF_APPS}' can only be used if {CONF_DEVICE_CLASS}' is '{DEVICE_CLASS_TV}'"
        )

    return config


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [vol.All(VIZIO_SCHEMA, validate_apps)])},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["media_player"]


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Component setup, run import config flow for each entry in config."""
    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    return unload_ok
