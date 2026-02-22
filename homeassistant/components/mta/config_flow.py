"""Config flow for MTA New York City Transit integration."""

from __future__ import annotations

import logging
from typing import Any

from pymta import LINE_TO_FEED, MTAFeedError, SubwayFeed
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_LINE, CONF_STOP_ID, CONF_STOP_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MTAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MTA."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.stops: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.data[CONF_LINE] = user_input[CONF_LINE]
            return await self.async_step_stop()

        lines = sorted(LINE_TO_FEED.keys())
        line_options = [SelectOptionDict(value=line, label=line) for line in lines]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LINE): SelectSelector(
                        SelectSelectorConfig(
                            options=line_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the stop step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID]
            self.data[CONF_STOP_ID] = stop_id
            stop_name = self.stops.get(stop_id, stop_id)
            self.data[CONF_STOP_NAME] = stop_name

            unique_id = f"{self.data[CONF_LINE]}_{stop_id}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Test connection to real-time GTFS-RT feed (different from static GTFS used by get_stops)
            try:
                await self._async_test_connection()
            except MTAFeedError:
                errors["base"] = "cannot_connect"
            else:
                title = f"{self.data[CONF_LINE]} Line - {stop_name}"
                return self.async_create_entry(
                    title=title,
                    data=self.data,
                )

        try:
            self.stops = await self._async_get_stops(self.data[CONF_LINE])
        except MTAFeedError:
            _LOGGER.exception("Error fetching stops for line %s", self.data[CONF_LINE])
            return self.async_abort(reason="cannot_connect")

        if not self.stops:
            _LOGGER.error("No stops found for line %s", self.data[CONF_LINE])
            return self.async_abort(reason="no_stops")

        stop_options = [
            SelectOptionDict(value=stop_id, label=stop_name)
            for stop_id, stop_name in sorted(self.stops.items(), key=lambda x: x[1])
        ]

        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=stop_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"line": self.data[CONF_LINE]},
        )

    async def _async_get_stops(self, line: str) -> dict[str, str]:
        """Get stops for a line from the library."""
        feed_id = SubwayFeed.get_feed_id_for_route(line)
        session = aiohttp_client.async_get_clientsession(self.hass)

        subway_feed = SubwayFeed(feed_id=feed_id, session=session)
        stops_list = await subway_feed.get_stops(route_id=line)

        stops = {}
        for stop in stops_list:
            stop_id = stop["stop_id"]
            stop_name = stop["stop_name"]
            # Add direction label (stop_id always ends in N or S)
            direction = stop_id[-1]
            stops[stop_id] = f"{stop_name} ({direction} direction)"

        return stops

    async def _async_test_connection(self) -> None:
        """Test connection to MTA feed."""
        feed_id = SubwayFeed.get_feed_id_for_route(self.data[CONF_LINE])
        session = aiohttp_client.async_get_clientsession(self.hass)

        subway_feed = SubwayFeed(feed_id=feed_id, session=session)
        await subway_feed.get_arrivals(
            route_id=self.data[CONF_LINE],
            stop_id=self.data[CONF_STOP_ID],
            max_arrivals=1,
        )
