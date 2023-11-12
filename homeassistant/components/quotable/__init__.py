"""The Quotable integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_UPDATE_FREQUENCY,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
)
from .services import register_services

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(ATTR_SELECTED_TAGS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(ATTR_SELECTED_AUTHORS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(
                    ATTR_UPDATE_FREQUENCY, default=DEFAULT_UPDATE_FREQUENCY
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Quotable integration."""

    quotable = hass.data.get(DOMAIN)

    if not quotable:
        static_config = config[DOMAIN]
        quotable = Quotable(
            static_config[ATTR_SELECTED_TAGS],
            static_config[ATTR_SELECTED_AUTHORS],
            static_config[ATTR_UPDATE_FREQUENCY],
        )

        hass.data[DOMAIN] = quotable

    register_services(hass)

    return True


class Quotable:
    """Quotable class."""

    selected_tags = list[str]
    selected_authors = list[str]
    update_frequency = int
    quotes = list[dict[str, Any]]

    def __init__(self, selected_tags, selected_authors, update_frequency):
        """Initialize Quotable."""
        self.quotes = []
        self.update_configuration(selected_tags, selected_authors, update_frequency)

    def update_configuration(self, selected_tags, selected_authors, update_frequency):
        """Update configuration."""
        self.selected_tags = selected_tags
        self.selected_authors = selected_authors
        self.update_frequency = update_frequency
