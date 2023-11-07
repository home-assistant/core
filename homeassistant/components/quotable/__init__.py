"""The Quotable integration."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_SELECTED_AUTHORS,
    CONF_SELECTED_TAGS,
    CONF_UPDATE_FREQUENCY,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_SELECTED_TAGS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_SELECTED_AUTHORS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(
                    CONF_UPDATE_FREQUENCY, default=DEFAULT_UPDATE_FREQUENCY
                ): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Quotable integration."""

    # conf = config[DOMAIN]

    hass.states.set(f"{DOMAIN}.testing", "It Works!")

    return True
