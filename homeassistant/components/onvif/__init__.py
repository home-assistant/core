"""The ONVIF integration."""
import asyncio

import voluptuous as vol

from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_per_platform

from .const import (
    CONF_PROFILE,
    CONF_RTSP_TRANSPORT,
    DEFAULT_ARGUMENTS,
    DEFAULT_PROFILE,
    DOMAIN,
    RTSP_TRANS_PROTOCOLS,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["camera"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the ONVIF component."""
    # Import from yaml
    configs = {}
    for p_type, p_config in config_per_platform(config, "camera"):
        if p_type != DOMAIN:
            continue

        config = p_config.copy()
        profile = config.get(CONF_PROFILE, DEFAULT_PROFILE)
        if config[CONF_HOST] not in configs.keys():
            configs[config[CONF_HOST]] = config
            configs[config[CONF_HOST]][CONF_PROFILE] = [profile]
        else:
            configs[config[CONF_HOST]][CONF_PROFILE].append(profile)

    for conf in configs.values():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up ONVIF from a config entry."""
    if not entry.options:
        await async_populate_options(hass, entry)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    return unload_ok


async def async_populate_options(hass, entry):
    """Populate default options for device."""
    options = {
        CONF_EXTRA_ARGUMENTS: DEFAULT_ARGUMENTS,
        CONF_RTSP_TRANSPORT: RTSP_TRANS_PROTOCOLS[0],
    }

    hass.config_entries.async_update_entry(entry, options=options)
