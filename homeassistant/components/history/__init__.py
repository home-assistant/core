"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from datetime import datetime as dt, timedelta
from http import HTTPStatus
import logging
import time
from typing import cast

from aiohttp import web
import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder import (
    DOMAIN as RECORDER_DOMAIN,
    get_instance,
    history,
)
from homeassistant.components.recorder.filters import (
    Filters,
    extract_include_exclude_filter_conf,
    merge_include_exclude_filters,
    sqlalchemy_filter_from_include_exclude_conf,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
)
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .const import (
    CONF_ORDER,
    DOMAIN,
    HISTORY_ENTITIES_FILTER,
    HISTORY_FILTERS,
    HISTORY_USE_INCLUDE_ORDER,
)
from .helpers import entities_may_have_state_changes_after
from .websocket_api import ws_get_history_during_period, ws_stream

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
            {vol.Optional(CONF_ORDER, default=False): cv.boolean}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the history hooks."""
    conf = config.get(DOMAIN, {})
    recorder_conf = config.get(RECORDER_DOMAIN, {})
    history_conf = config.get(DOMAIN, {})
    recorder_filter = extract_include_exclude_filter_conf(recorder_conf)
    logbook_filter = extract_include_exclude_filter_conf(history_conf)
    merged_filter = merge_include_exclude_filters(recorder_filter, logbook_filter)

    possible_merged_entities_filter = convert_include_exclude_filter(merged_filter)

    if not possible_merged_entities_filter.empty_filter:
        hass.data[
            HISTORY_FILTERS
        ] = filters = sqlalchemy_filter_from_include_exclude_conf(conf)
        hass.data[HISTORY_ENTITIES_FILTER] = possible_merged_entities_filter
    else:
        hass.data[HISTORY_FILTERS] = filters = None
        hass.data[HISTORY_ENTITIES_FILTER] = None

    hass.data[HISTORY_USE_INCLUDE_ORDER] = use_include_order = conf.get(CONF_ORDER)

    hass.http.register_view(HistoryPeriodView(filters, use_include_order))
    frontend.async_register_built_in_panel(hass, "history", "history", "hass:chart-box")
    websocket_api.async_register_command(hass, ws_get_history_during_period)
    websocket_api.async_register_command(hass, ws_stream)

    return True


class HistoryPeriodView(HomeAssistantView):
    """Handle history period requests."""

    url = "/api/history/period"
    name = "api:history:view-period"
    extra_urls = ["/api/history/period/{datetime}"]

    def __init__(self, filters: Filters | None, use_include_order: bool) -> None:
        """Initialize the history period view."""
        self.filters = filters
        self.use_include_order = use_include_order

    async def get(
        self, request: web.Request, datetime: str | None = None
    ) -> web.Response:
        """Return history over a period of time."""
        datetime_ = None
        if datetime and (datetime_ := dt_util.parse_datetime(datetime)) is None:
            return self.json_message("Invalid datetime", HTTPStatus.BAD_REQUEST)

        now = dt_util.utcnow()

        one_day = timedelta(days=1)
        if datetime_:
            start_time = dt_util.as_utc(datetime_)
        else:
            start_time = now - one_day

        if start_time > now:
            return self.json([])

        if end_time_str := request.query.get("end_time"):
            if end_time := dt_util.parse_datetime(end_time_str):
                end_time = dt_util.as_utc(end_time)
            else:
                return self.json_message("Invalid end_time", HTTPStatus.BAD_REQUEST)
        else:
            end_time = start_time + one_day
        entity_ids_str = request.query.get("filter_entity_id")
        entity_ids = None
        if entity_ids_str:
            entity_ids = entity_ids_str.lower().split(",")
        include_start_time_state = "skip_initial_state" not in request.query
        significant_changes_only = (
            request.query.get("significant_changes_only", "1") != "0"
        )

        minimal_response = "minimal_response" in request.query
        no_attributes = "no_attributes" in request.query

        hass = request.app["hass"]

        if (
            not include_start_time_state
            and entity_ids
            and not entities_may_have_state_changes_after(
                hass, entity_ids, start_time, no_attributes
            )
        ):
            return self.json([])

        return cast(
            web.Response,
            await get_instance(hass).async_add_executor_job(
                self._sorted_significant_states_json,
                hass,
                start_time,
                end_time,
                entity_ids,
                include_start_time_state,
                significant_changes_only,
                minimal_response,
                no_attributes,
            ),
        )

    def _sorted_significant_states_json(
        self,
        hass: HomeAssistant,
        start_time: dt,
        end_time: dt,
        entity_ids: list[str] | None,
        include_start_time_state: bool,
        significant_changes_only: bool,
        minimal_response: bool,
        no_attributes: bool,
    ) -> web.Response:
        """Fetch significant stats from the database as json."""
        timer_start = time.perf_counter()

        with session_scope(hass=hass) as session:
            states = history.get_significant_states_with_session(
                hass,
                session,
                start_time,
                end_time,
                entity_ids,
                self.filters,
                include_start_time_state,
                significant_changes_only,
                minimal_response,
                no_attributes,
            )

        if _LOGGER.isEnabledFor(logging.DEBUG):
            elapsed = time.perf_counter() - timer_start
            _LOGGER.debug(
                "Extracted %d states in %fs", sum(map(len, states.values())), elapsed
            )

        # Optionally reorder the result to respect the ordering given
        # by any entities explicitly included in the configuration.
        if not self.filters or not self.use_include_order:
            return self.json(list(states.values()))

        sorted_result = [
            states.pop(order_entity)
            for order_entity in self.filters.included_entities
            if order_entity in states
        ]
        sorted_result.extend(list(states.values()))
        return self.json(sorted_result)
