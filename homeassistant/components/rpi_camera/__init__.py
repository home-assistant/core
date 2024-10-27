"""The rpi_camera component."""

import voluptuous as vol

from homeassistant.const import CONF_FILE_PATH, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HORIZONTAL_FLIP,
    CONF_IMAGE_HEIGHT,
    CONF_IMAGE_QUALITY,
    CONF_IMAGE_ROTATION,
    CONF_IMAGE_WIDTH,
    CONF_OVERLAY_METADATA,
    CONF_OVERLAY_TIMESTAMP,
    CONF_TIMELAPSE,
    CONF_VERTICAL_FLIP,
    DEFAULT_HORIZONTAL_FLIP,
    DEFAULT_IMAGE_HEIGHT,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_IMAGE_ROTATION,
    DEFAULT_IMAGE_WIDTH,
    DEFAULT_NAME,
    DEFAULT_TIMELAPSE,
    DEFAULT_VERTICAL_FLIP,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_FILE_PATH): cv.isfile,
                vol.Optional(
                    CONF_HORIZONTAL_FLIP, default=DEFAULT_HORIZONTAL_FLIP
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
                vol.Optional(
                    CONF_IMAGE_HEIGHT, default=DEFAULT_IMAGE_HEIGHT
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_IMAGE_QUALITY, default=DEFAULT_IMAGE_QUALITY
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                vol.Optional(
                    CONF_IMAGE_ROTATION, default=DEFAULT_IMAGE_ROTATION
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=359)),
                vol.Optional(CONF_IMAGE_WIDTH, default=DEFAULT_IMAGE_WIDTH): vol.Coerce(
                    int
                ),
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_OVERLAY_METADATA): vol.All(
                    vol.Coerce(int), vol.Range(min=4, max=2056)
                ),
                vol.Optional(CONF_OVERLAY_TIMESTAMP): cv.string,
                vol.Optional(CONF_TIMELAPSE, default=DEFAULT_TIMELAPSE): vol.Coerce(
                    int
                ),
                vol.Optional(
                    CONF_VERTICAL_FLIP, default=DEFAULT_VERTICAL_FLIP
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the rpi_camera integration."""
    config_domain = config[DOMAIN]
    hass.data[DOMAIN] = {
        CONF_FILE_PATH: config_domain.get(CONF_FILE_PATH),
        CONF_HORIZONTAL_FLIP: config_domain.get(CONF_HORIZONTAL_FLIP),
        CONF_IMAGE_WIDTH: config_domain.get(CONF_IMAGE_WIDTH),
        CONF_IMAGE_HEIGHT: config_domain.get(CONF_IMAGE_HEIGHT),
        CONF_IMAGE_QUALITY: config_domain.get(CONF_IMAGE_QUALITY),
        CONF_IMAGE_ROTATION: config_domain.get(CONF_IMAGE_ROTATION),
        CONF_NAME: config_domain.get(CONF_NAME),
        CONF_OVERLAY_METADATA: config_domain.get(CONF_OVERLAY_METADATA),
        CONF_OVERLAY_TIMESTAMP: config_domain.get(CONF_OVERLAY_TIMESTAMP),
        CONF_TIMELAPSE: config_domain.get(CONF_TIMELAPSE),
        CONF_VERTICAL_FLIP: config_domain.get(CONF_VERTICAL_FLIP),
    }

    discovery.load_platform(hass, Platform.CAMERA, DOMAIN, {}, config)

    return True
