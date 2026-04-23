"""Config flow for MTA New York City Transit integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pymta import LINE_TO_FEED, BusFeed, MTAFeedError, SubwayFeed
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_LINE,
    CONF_ROUTE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_BUS,
    SUBENTRY_TYPE_SUBWAY,
)

_LOGGER = logging.getLogger(__name__)


class MTAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MTA."""

    VERSION = 1
    MINOR_VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            SUBENTRY_TYPE_SUBWAY: SubwaySubentryFlowHandler,
            SUBENTRY_TYPE_BUS: BusSubentryFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY)
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            if api_key:
                # Test the API key by trying to fetch bus data
                session = async_get_clientsession(self.hass)
                bus_feed = BusFeed(api_key=api_key, session=session)
                try:
                    # Try to get stops for a known route to validate the key
                    await bus_feed.get_stops(route_id="M15")
                except MTAFeedError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error validating API key")
                    errors["base"] = "unknown"
            if not errors:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={CONF_API_KEY: api_key or None},
                    )
                return self.async_create_entry(
                    title="MTA",
                    data={CONF_API_KEY: api_key or None},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when user wants to add or update API key."""
        return await self.async_step_user()


class SubwaySubentryFlowHandler(ConfigSubentryFlow):
    """Handle subway stop subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.data: dict[str, Any] = {}
        self.stops: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the line selection step."""
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
        )

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the stop selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID]
            self.data[CONF_STOP_ID] = stop_id
            stop_name = self.stops.get(stop_id, stop_id)
            self.data[CONF_STOP_NAME] = stop_name

            unique_id = f"{self.data[CONF_LINE]}_{stop_id}"

            # Check for duplicate subentries across all entries
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                for subentry in entry.subentries.values():
                    if subentry.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")

            # Test connection to real-time GTFS-RT feed
            try:
                await self._async_test_connection()
            except MTAFeedError:
                errors["base"] = "cannot_connect"
            else:
                title = f"{self.data[CONF_LINE]} - {stop_name}"
                return self.async_create_entry(
                    title=title,
                    data=self.data,
                    unique_id=unique_id,
                )

        try:
            self.stops = await self._async_get_stops(self.data[CONF_LINE])
        except MTAFeedError:
            _LOGGER.debug("Error fetching stops for line %s", self.data[CONF_LINE])
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
        session = async_get_clientsession(self.hass)

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
        session = async_get_clientsession(self.hass)

        subway_feed = SubwayFeed(feed_id=feed_id, session=session)
        await subway_feed.get_arrivals(
            route_id=self.data[CONF_LINE],
            stop_id=self.data[CONF_STOP_ID],
            max_arrivals=1,
        )


class BusSubentryFlowHandler(ConfigSubentryFlow):
    """Handle bus stop subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.data: dict[str, Any] = {}
        self.stops: dict[str, str] = {}

    def _get_api_key(self) -> str:
        """Get API key from parent entry."""
        return self._get_entry().data.get(CONF_API_KEY) or ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the route input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            route = user_input[CONF_ROUTE].upper().strip()
            self.data[CONF_ROUTE] = route

            # Validate route by fetching stops
            try:
                self.stops = await self._async_get_stops(route)
                if not self.stops:
                    errors["base"] = "invalid_route"
                else:
                    return await self.async_step_stop()
            except MTAFeedError:
                _LOGGER.debug("Error fetching stops for route %s", route)
                errors["base"] = "invalid_route"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROUTE): TextSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the stop selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID]
            self.data[CONF_STOP_ID] = stop_id
            stop_name = self.stops.get(stop_id, stop_id)
            self.data[CONF_STOP_NAME] = stop_name

            unique_id = f"bus_{self.data[CONF_ROUTE]}_{stop_id}"

            # Check for duplicate subentries across all entries
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                for subentry in entry.subentries.values():
                    if subentry.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")

            # Test connection to real-time feed
            try:
                await self._async_test_connection()
            except MTAFeedError:
                errors["base"] = "cannot_connect"
            else:
                title = f"{self.data[CONF_ROUTE]} - {stop_name}"
                return self.async_create_entry(
                    title=title,
                    data=self.data,
                    unique_id=unique_id,
                )

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
            description_placeholders={"route": self.data[CONF_ROUTE]},
        )

    async def _async_get_stops(self, route: str) -> dict[str, str]:
        """Get stops for a bus route from the library."""
        session = async_get_clientsession(self.hass)
        api_key = self._get_api_key()

        bus_feed = BusFeed(api_key=api_key, session=session)
        stops_list = await bus_feed.get_stops(route_id=route)

        stops = {}
        for stop in stops_list:
            stop_id = stop["stop_id"]
            stop_name = stop["stop_name"]
            # Add direction if available (e.g., "to South Ferry")
            if direction := stop.get("direction_name"):
                stops[stop_id] = f"{stop_name} (to {direction})"
            else:
                stops[stop_id] = stop_name

        return stops

    async def _async_test_connection(self) -> None:
        """Test connection to MTA bus feed."""
        session = async_get_clientsession(self.hass)
        api_key = self._get_api_key()

        bus_feed = BusFeed(api_key=api_key, session=session)
        await bus_feed.get_arrivals(
            route_id=self.data[CONF_ROUTE],
            stop_id=self.data[CONF_STOP_ID],
            max_arrivals=1,
        )
