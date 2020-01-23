"""The vizio component."""
import asyncio

import voluptuous as vol

from homeassistant.components.media_player import DEVICE_CLASS_TV
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DEVICE_CLASS
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN, VIZIO_SCHEMA


def validate_auth(config: ConfigType) -> ConfigType:
    """Validate presence of CONF_ACCESS_TOKEN when CONF_DEVICE_CLASS == DEVICE_CLASS_TV."""
    token = config.get(CONF_ACCESS_TOKEN)
    if config[CONF_DEVICE_CLASS] == DEVICE_CLASS_TV and not token:
        raise vol.Invalid(
            f"When '{CONF_DEVICE_CLASS}' is '{DEVICE_CLASS_TV}' then "
            f"'{CONF_ACCESS_TOKEN}' is required.",
            path=[CONF_ACCESS_TOKEN],
        )

    return config


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list, [vol.All(vol.Schema(VIZIO_SCHEMA), validate_auth)]
        )
    },
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
