"""The Quotable integration."""

import logging
import time
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_QUOTES,
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_UPDATE_FREQUENCY,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
    ENTITY_ID,
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
        quotable = Quotable(hass, config[DOMAIN])
        hass.data[DOMAIN] = quotable

    register_services(hass)

    return True


class Quotable:
    """Quotable class."""

    def __init__(self, hass, config):
        """Initialize Quotable."""
        self.hass = hass
        self.quotes = []
        self.config = config
        self._update_state()

    def update_configuration(self, selected_tags, selected_authors, update_frequency):
        """Update configuration."""
        self.config[ATTR_SELECTED_TAGS] = selected_tags
        self.config[ATTR_SELECTED_AUTHORS] = selected_authors
        self.config[ATTR_UPDATE_FREQUENCY] = update_frequency
        self._update_state()

    @property
    def attrs(self) -> dict[str, Any]:
        """Attributes that are saved in state."""
        return {**self.config, **{ATTR_QUOTES: self.quotes}}

    def _update_state(self):
        self.hass.states.set(ENTITY_ID, time.time(), self.attrs)
