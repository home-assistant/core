"""The Quotable integration."""

from datetime import datetime, timedelta
import json
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BG_COLOR,
    ATTR_QUOTES,
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_STYLES,
    ATTR_TEXT_COLOR,
    ATTR_UPDATE_FREQUENCY,
    DEFAULT_BG_COLOR,
    DEFAULT_TEXT_COLOR,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
    ENTITY_ID,
    EVENT_NEW_QUOTE_FETCHED,
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
                vol.Optional(ATTR_STYLES, default={}): vol.Schema(
                    {
                        vol.Optional(
                            ATTR_BG_COLOR, default=DEFAULT_BG_COLOR
                        ): cv.string,
                        vol.Optional(
                            ATTR_TEXT_COLOR, default=DEFAULT_TEXT_COLOR
                        ): cv.string,
                    }
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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
        self._hass = hass
        self.config = config
        self.quotes = []
        self._update_state()

        self._unsubscribe_fetch_a_quote = None
        self._subscribe_fetch_a_quote()
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._cancel_async_event_listeners
        )

        self._hass.bus.async_listen(
            EVENT_NEW_QUOTE_FETCHED, self._handle_new_quote_fetched
        )

    @property
    def attrs(self) -> dict[str, Any]:
        """Attributes that are saved in state."""
        return {**self.config, **{ATTR_QUOTES: json.dumps(self.quotes)}}

    def update_configuration(
        self, selected_tags, selected_authors, update_frequency, styles
    ):
        """Update configuration."""
        self.config[ATTR_SELECTED_TAGS] = selected_tags
        self.config[ATTR_SELECTED_AUTHORS] = selected_authors
        self.config[ATTR_STYLES] = styles

        if self.config[ATTR_UPDATE_FREQUENCY] != update_frequency:
            self.config[ATTR_UPDATE_FREQUENCY] = update_frequency
            # Recreate event listener only if update_frequency is changed
            self._subscribe_fetch_a_quote()

        self._update_state()

    def _update_state(self):
        self._hass.states.async_set(ENTITY_ID, datetime.now(), self.attrs)

    def _handle_new_quote_fetched(self, event: Event):
        self.quotes.insert(0, event.data)

        if len(self.quotes) > 10:
            self.quotes.pop()

        self._update_state()

    def _subscribe_fetch_a_quote(self):
        if self._unsubscribe_fetch_a_quote:
            self._unsubscribe_fetch_a_quote()

        self._unsubscribe_fetch_a_quote = async_track_time_interval(
            self._hass,
            self._schedule_fetch_a_quote_task,
            timedelta(seconds=self.config[ATTR_UPDATE_FREQUENCY]),
            cancel_on_shutdown=True,
        )

    @callback
    def _cancel_async_event_listeners(self, _: Event):
        self._unsubscribe_fetch_a_quote()

    @callback
    def _schedule_fetch_a_quote_task(self, _: datetime) -> None:
        self._hass.async_create_task(
            self._hass.services.async_call(DOMAIN, SERVICE_FETCH_A_QUOTE)
        )
