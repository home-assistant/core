"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt, timedelta
import logging
import time
from typing import cast

from aiohttp import web
from sqlalchemy import not_, or_
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder import history, models as history_models
from homeassistant.components.recorder.statistics import (
    list_statistic_ids,
    statistics_during_period,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_INCLUDE,
    HTTP_BAD_REQUEST,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.deprecation import deprecated_class, deprecated_function
from homeassistant.helpers.entityfilter import (
    CONF_ENTITY_GLOBS,
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
)
import homeassistant.util.dt as dt_util

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

DOMAIN = "history"
CONF_ORDER = "use_include_order"

GLOB_TO_SQL_CHARS = {
    42: "%",  # *
    46: "_",  # .
}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
            {vol.Optional(CONF_ORDER, default=False): cv.boolean}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@deprecated_function("homeassistant.components.recorder.history.get_significant_states")
def get_significant_states(hass, *args, **kwargs):
    """Wrap _get_significant_states with an sql session."""
    return history.get_significant_states(hass, *args, **kwargs)


@deprecated_function(
    "homeassistant.components.recorder.history.state_changes_during_period"
)
def state_changes_during_period(hass, start_time, end_time=None, entity_id=None):
    """Return states changes during UTC period start_time - end_time."""
    return history.state_changes_during_period(
        hass, start_time, end_time=None, entity_id=None
    )


@deprecated_function("homeassistant.components.recorder.history.get_last_state_changes")
def get_last_state_changes(hass, number_of_states, entity_id):
    """Return the last number_of_states."""
    return history.get_last_state_changes(hass, number_of_states, entity_id)


@deprecated_function("homeassistant.components.recorder.history.get_states")
def get_states(hass, utc_point_in_time, entity_ids=None, run=None, filters=None):
    """Return the states at a specific point in time."""
    return history.get_states(
        hass, utc_point_in_time, entity_ids=None, run=None, filters=None
    )


@deprecated_function("homeassistant.components.recorder.history.get_state")
def get_state(hass, utc_point_in_time, entity_id, run=None):
    """Return a state at a specific point in time."""
    return history.get_state(hass, utc_point_in_time, entity_id, run=None)


async def async_setup(hass, config):
    """Set up the history hooks."""
    conf = config.get(DOMAIN, {})

    filters = sqlalchemy_filter_from_include_exclude_conf(conf)

    use_include_order = conf.get(CONF_ORDER)

    hass.http.register_view(HistoryPeriodView(filters, use_include_order))
    hass.components.frontend.async_register_built_in_panel(
        "history", "history", "hass:poll-box"
    )
    hass.components.websocket_api.async_register_command(
        ws_get_statistics_during_period
    )
    hass.components.websocket_api.async_register_command(ws_get_list_statistic_ids)

    return True


@deprecated_class("homeassistant.components.recorder.models.LazyState")
class LazyState(history_models.LazyState):
    """A lazy version of core State."""


@websocket_api.websocket_command(
    {
        vol.Required("type"): "history/statistics_during_period",
        vol.Required("start_time"): str,
        vol.Optional("end_time"): str,
        vol.Optional("statistic_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_get_statistics_during_period(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle statistics websocket command."""
    start_time_str = msg["start_time"]
    end_time_str = msg.get("end_time")

    start_time = dt_util.parse_datetime(start_time_str)
    if start_time:
        start_time = dt_util.as_utc(start_time)
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start_time")
        return

    if end_time_str:
        end_time = dt_util.parse_datetime(end_time_str)
        if end_time:
            end_time = dt_util.as_utc(end_time)
        else:
            connection.send_error(msg["id"], "invalid_end_time", "Invalid end_time")
            return
    else:
        end_time = None

    statistics = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        start_time,
        end_time,
        msg.get("statistic_ids"),
    )
    connection.send_result(msg["id"], statistics)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "history/list_statistic_ids",
        vol.Optional("statistic_type"): vol.Any("sum", "mean"),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_get_list_statistic_ids(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Fetch a list of available statistic_id."""
    statistic_ids = await hass.async_add_executor_job(
        list_statistic_ids,
        hass,
        msg.get("statistic_type"),
    )
    connection.send_result(msg["id"], statistic_ids)


class HistoryPeriodView(HomeAssistantView):
    """Handle history period requests."""

    url = "/api/history/period"
    name = "api:history:view-period"
    extra_urls = ["/api/history/period/{datetime}"]

    def __init__(self, filters, use_include_order):
        """Initialize the history period view."""
        self.filters = filters
        self.use_include_order = use_include_order

    async def get(
        self, request: web.Request, datetime: str | None = None
    ) -> web.Response:
        """Return history over a period of time."""
        datetime_ = None
        if datetime:
            datetime_ = dt_util.parse_datetime(datetime)

            if datetime_ is None:
                return self.json_message("Invalid datetime", HTTP_BAD_REQUEST)

        now = dt_util.utcnow()

        one_day = timedelta(days=1)
        if datetime_:
            start_time = dt_util.as_utc(datetime_)
        else:
            start_time = now - one_day

        if start_time > now:
            return self.json([])

        end_time_str = request.query.get("end_time")
        if end_time_str:
            end_time = dt_util.parse_datetime(end_time_str)
            if end_time:
                end_time = dt_util.as_utc(end_time)
            else:
                return self.json_message("Invalid end_time", HTTP_BAD_REQUEST)
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

        hass = request.app["hass"]

        if (
            not include_start_time_state
            and entity_ids
            and not _entities_may_have_state_changes_after(hass, entity_ids, start_time)
        ):
            return self.json([])

        return cast(
            web.Response,
            await hass.async_add_executor_job(
                self._sorted_significant_states_json,
                hass,
                start_time,
                end_time,
                entity_ids,
                include_start_time_state,
                significant_changes_only,
                minimal_response,
            ),
        )

    def _sorted_significant_states_json(
        self,
        hass,
        start_time,
        end_time,
        entity_ids,
        include_start_time_state,
        significant_changes_only,
        minimal_response,
    ):
        """Fetch significant stats from the database as json."""
        timer_start = time.perf_counter()

        with session_scope(hass=hass) as session:
            result = (
                history._get_significant_states(  # pylint: disable=protected-access
                    hass,
                    session,
                    start_time,
                    end_time,
                    entity_ids,
                    self.filters,
                    include_start_time_state,
                    significant_changes_only,
                    minimal_response,
                )
            )

        result = list(result.values())
        if _LOGGER.isEnabledFor(logging.DEBUG):
            elapsed = time.perf_counter() - timer_start
            _LOGGER.debug("Extracted %d states in %fs", sum(map(len, result)), elapsed)

        # Optionally reorder the result to respect the ordering given
        # by any entities explicitly included in the configuration.
        if self.filters and self.use_include_order:
            sorted_result = []
            for order_entity in self.filters.included_entities:
                for state_list in result:
                    if state_list[0].entity_id == order_entity:
                        sorted_result.append(state_list)
                        result.remove(state_list)
                        break
            sorted_result.extend(result)
            result = sorted_result

        return self.json(result)


def sqlalchemy_filter_from_include_exclude_conf(conf):
    """Build a sql filter from config."""
    filters = Filters()
    exclude = conf.get(CONF_EXCLUDE)
    if exclude:
        filters.excluded_entities = exclude.get(CONF_ENTITIES, [])
        filters.excluded_domains = exclude.get(CONF_DOMAINS, [])
        filters.excluded_entity_globs = exclude.get(CONF_ENTITY_GLOBS, [])
    include = conf.get(CONF_INCLUDE)
    if include:
        filters.included_entities = include.get(CONF_ENTITIES, [])
        filters.included_domains = include.get(CONF_DOMAINS, [])
        filters.included_entity_globs = include.get(CONF_ENTITY_GLOBS, [])

    return filters if filters.has_config else None


class Filters:
    """Container for the configured include and exclude filters."""

    def __init__(self):
        """Initialise the include and exclude filters."""
        self.excluded_entities = []
        self.excluded_domains = []
        self.excluded_entity_globs = []

        self.included_entities = []
        self.included_domains = []
        self.included_entity_globs = []

    def apply(self, query):
        """Apply the entity filter."""
        if not self.has_config:
            return query

        return query.filter(self.entity_filter())

    @property
    def has_config(self):
        """Determine if there is any filter configuration."""
        if (
            self.excluded_entities
            or self.excluded_domains
            or self.excluded_entity_globs
            or self.included_entities
            or self.included_domains
            or self.included_entity_globs
        ):
            return True

        return False

    def bake(self, baked_query):
        """Update a baked query.

        Works the same as apply on a baked_query.
        """
        if not self.has_config:
            return

        baked_query += lambda q: q.filter(self.entity_filter())

    def entity_filter(self):
        """Generate the entity filter query."""
        includes = []
        if self.included_domains:
            includes.append(history_models.States.domain.in_(self.included_domains))
        if self.included_entities:
            includes.append(history_models.States.entity_id.in_(self.included_entities))
        for glob in self.included_entity_globs:
            includes.append(_glob_to_like(glob))

        excludes = []
        if self.excluded_domains:
            excludes.append(history_models.States.domain.in_(self.excluded_domains))
        if self.excluded_entities:
            excludes.append(history_models.States.entity_id.in_(self.excluded_entities))
        for glob in self.excluded_entity_globs:
            excludes.append(_glob_to_like(glob))

        if not includes and not excludes:
            return None

        if includes and not excludes:
            return or_(*includes)

        if not excludes and includes:
            return not_(or_(*excludes))

        return or_(*includes) & not_(or_(*excludes))


def _glob_to_like(glob_str):
    """Translate glob to sql."""
    return history_models.States.entity_id.like(glob_str.translate(GLOB_TO_SQL_CHARS))


def _entities_may_have_state_changes_after(
    hass: HomeAssistant, entity_ids: Iterable, start_time: dt
) -> bool:
    """Check the state machine to see if entities have changed since start time."""
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)

        if state is None or state.last_changed > start_time:
            return True

    return False
