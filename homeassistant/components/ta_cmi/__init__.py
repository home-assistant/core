"""The Technische Alternative C.M.I. integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CHANNELS,
    CONF_CHANNELS_DEVICE_CLASS,
    CONF_CHANNELS_ID,
    CONF_CHANNELS_NAME,
    CONF_CHANNELS_TYPE,
    CONF_DEVICE_FETCH_MODE,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    DOMAIN,
)

PLATFORMS: list[str] = ["sensor"]

CHANNEL_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_CHANNELS_TYPE): vol.In(["input", "output"]),
        vol.Required(CONF_CHANNELS_ID): cv.positive_int,
        vol.Required(CONF_CHANNELS_NAME): cv.string,
        vol.Optional(CONF_CHANNELS_DEVICE_CLASS, default=""): cv.string,
    }
)

DEVICE_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.positive_int,
        vol.Optional(CONF_CHANNELS): vol.All(cv.ensure_list, [CHANNEL_SCHEMA]),
        vol.Optional(CONF_DEVICE_FETCH_MODE, default="all"): vol.In(["all", "defined"]),
    }
)

PLATFORM_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
    }
)


def setup(hass, config):
    """Set up the C.M.I. component."""
    # Data that you want to share with your platforms
    hass.data[DOMAIN] = config[DOMAIN][0]

    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, config)

    return True
