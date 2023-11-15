"""The Quotable integration."""

from datetime import datetime, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_QUOTES,
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_UPDATE_FREQUENCY,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
    ENTITY_ID,
    SERVICE_FETCH_A_QUOTE,
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

    register_services(hass)

    quotable = hass.data.get(DOMAIN)

    if not quotable:
        quotable = Quotable(hass, config[DOMAIN])
        hass.data[DOMAIN] = quotable

    return True


class Quotable:
    """Quotable class."""

    def __init__(self, hass, config):
        """Initialize Quotable."""
        self._hass = hass
        self.quotes = []
        self.config = config
        self._unsubscribe = None
        self._add_event_listener()
        self._update_state()
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._cancel_event_listener
        )

    @property
    def attrs(self) -> dict[str, Any]:
        """Attributes that are saved in state."""
        return {**self.config, **{ATTR_QUOTES: self.quotes}}

    def update_configuration(self, selected_tags, selected_authors, update_frequency):
        """Update configuration."""

        self.config[ATTR_SELECTED_TAGS] = selected_tags
        self.config[ATTR_SELECTED_AUTHORS] = selected_authors

        if self.config[ATTR_UPDATE_FREQUENCY] != update_frequency:
            self.config[ATTR_UPDATE_FREQUENCY] = update_frequency
            # Recreate event listener only if update_frequency is changed
            self._add_event_listener()

        self._update_state()

    def _update_state(self):
        self._hass.states.set(ENTITY_ID, datetime.now(), self.attrs)

    def _add_event_listener(self):
        self._cancel_event_listener(self)

        self._unsubscribe = async_track_time_interval(
            self._hass,
            self._schedule_fetch_a_quote_task,
            timedelta(seconds=self.config[ATTR_UPDATE_FREQUENCY]),
            cancel_on_shutdown=True,
        )

    @callback
    def _cancel_event_listener(self, _: Event):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _schedule_fetch_a_quote_task(self, _: datetime) -> None:
        self._hass.async_create_task(
            self._hass.services.async_call(DOMAIN, SERVICE_FETCH_A_QUOTE)
        )
