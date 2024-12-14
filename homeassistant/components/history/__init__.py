"""Provide pre-made queries on top of the recorder component."""

from __future__ import annotations

from datetime import datetime as dt, timedelta
from http import HTTPStatus
from typing import cast

from aiohttp import web
import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.recorder import get_instance, history
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant, valid_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from . import websocket_api
from .const import DOMAIN
from .helpers import entities_may_have_state_changes_after, has_states_before

CONF_ORDER = "use_include_order"
ONE_DAY = timedelta(days=1)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_INCLUDE),
            cv.deprecated(CONF_EXCLUDE),
            cv.deprecated(CONF_ORDER),
            INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
                {vol.Optional(CONF_ORDER, default=False): cv.boolean}
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the history integration.

    This registers HTTP endpoints and websocket APIs for retrieving
    and managing historical state data from the recorder component.
    """
    hass.http.register_view(HistoryPeriodView())
    frontend.async_register_built_in_panel(hass, "history", "history", "hass:chart-box")
    websocket_api.async_setup(hass)
    return True


class HistoryPeriodView(HomeAssistantView):
    """Handle requests for historical state data."""

    url = "/api/history/period"
    name = "api:history:view-period"
    extra_urls = ["/api/history/period/{datetime}"]

    async def get(
        self, request: web.Request, datetime: str | None = None
    ) -> web.Response:
        """Fetch historical state data for specified entities.

        Args:
            request (web.Request): The HTTP request with query parameters.
            datetime (str | None): Optional datetime string from the URL.

        Returns:
            web.Response: JSON response containing historical state data or error messages.

        """
        datetime_parsed = None
        query = request.query

        # Parse datetime from the URL
        if datetime and (datetime_parsed := dt_util.parse_datetime(datetime)) is None:
            return self.json_message("Invalid datetime", HTTPStatus.BAD_REQUEST)

        # Extract and validate entity IDs from query parameters
        if not (entity_ids_raw := query.get("filter_entity_id")) or not (
            entity_ids := entity_ids_raw.strip().lower().split(",")
        ):
            return self.json_message(
                "filter_entity_id is missing", HTTPStatus.BAD_REQUEST
            )

        hass = request.app[KEY_HASS]

        for entity_id in entity_ids:
            if not hass.states.get(entity_id) and not valid_entity_id(entity_id):
                return self.json_message(
                    "Invalid filter_entity_id", HTTPStatus.BAD_REQUEST
                )

        # Determine start and end times for fetching history
        now = dt_util.utcnow()
        if datetime_parsed:
            start_time = dt_util.as_utc(datetime_parsed)
        else:
            start_time = now - ONE_DAY

        if start_time > now:
            return self.json([])

        if end_time_raw := query.get("end_time"):
            if end_time := dt_util.parse_datetime(end_time_raw):
                end_time = dt_util.as_utc(end_time)
            else:
                return self.json_message("Invalid end_time", HTTPStatus.BAD_REQUEST)
        else:
            end_time = start_time + ONE_DAY

        # Determine additional query options
        include_initial_state = "skip_initial_state" not in query
        significant_changes_only = query.get("significant_changes_only", "1") != "0"
        minimal_response = "minimal_response" in query
        exclude_attributes = "no_attributes" in query

        # If there are no states before end_time or no significant changes, return an empty response
        if (
            (end_time and not has_states_before(hass, end_time))
            or not include_initial_state
            and entity_ids
            and not entities_may_have_state_changes_after(
                hass, entity_ids, start_time, exclude_attributes
            )
        ):
            return self.json([])

        # Fetch and return significant states from the database
        return cast(
            web.Response,
            await get_instance(hass).async_add_executor_job(
                self._fetch_significant_states,
                hass,
                start_time,
                end_time,
                entity_ids,
                include_initial_state,
                significant_changes_only,
                minimal_response,
                exclude_attributes,
            ),
        )

    def _fetch_significant_states(
        self,
        hass: HomeAssistant,
        start_time: dt,
        end_time: dt,
        entity_ids: list[str],
        include_initial_state: bool,
        significant_changes_only: bool,
        minimal_response: bool,
        exclude_attributes: bool,
    ) -> web.Response:
        """Retrieve significant state changes from the database.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            start_time (dt): The start time for the query.
            end_time (dt): The end time for the query.
            entity_ids (list[str]): List of entity IDs to query.
            include_initial_state (bool): Whether to include the initial state.
            significant_changes_only (bool): Whether to include only significant changes.
            minimal_response (bool): Whether to return minimal response data.
            exclude_attributes (bool): Whether to exclude attributes.

        Returns:
            web.Response: JSON response containing significant state changes.

        """
        with session_scope(hass=hass, read_only=True) as session:
            significant_states = history.get_significant_states_with_session(
                hass,
                session,
                start_time,
                end_time,
                entity_ids,
                None,
                include_initial_state,
                significant_changes_only,
                minimal_response,
                exclude_attributes,
            )
            return self.json(list(significant_states.values()))
