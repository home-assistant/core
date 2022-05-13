"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt, timedelta
from http import HTTPStatus
import logging
import time
from typing import Any, Literal, cast

from aiohttp import web
from sqlalchemy import not_, or_
from sqlalchemy.ext.baked import BakedQuery
from sqlalchemy.orm import Query
import voluptuous as vol

from homeassistant.components import frontend, websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.recorder import (
    get_instance,
    history,
    models as history_models,
)
from homeassistant.components.recorder.statistics import (
    list_statistic_ids,
    statistics_during_period,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.websocket_api import messages
from homeassistant.components.websocket_api.const import JSON_DUMP
from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    CONF_ENTITY_GLOBS,
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
)
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "history"
HISTORY_FILTERS = "history_filters"
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the history hooks."""
    conf = config.get(DOMAIN, {})

    hass.data[HISTORY_FILTERS] = filters = sqlalchemy_filter_from_include_exclude_conf(
        conf
    )

    use_include_order = conf.get(CONF_ORDER)

    hass.http.register_view(HistoryPeriodView(filters, use_include_order))
    frontend.async_register_built_in_panel(hass, "history", "history", "hass:chart-box")
    websocket_api.async_register_command(hass, ws_get_statistics_during_period)
    websocket_api.async_register_command(hass, ws_get_list_statistic_ids)
    websocket_api.async_register_command(hass, ws_get_history_during_period)

    return True


def _ws_get_statistics_during_period(
    hass: HomeAssistant,
    msg_id: int,
    start_time: dt,
    end_time: dt | None = None,
    statistic_ids: list[str] | None = None,
    period: Literal["5minute", "day", "hour", "month"] = "hour",
) -> str:
    """Fetch statistics and convert them to json in the executor."""
    return JSON_DUMP(
        messages.result_message(
            msg_id,
            statistics_during_period(hass, start_time, end_time, statistic_ids, period),
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "history/statistics_during_period",
        vol.Required("start_time"): str,
        vol.Optional("end_time"): str,
        vol.Optional("statistic_ids"): [str],
        vol.Required("period"): vol.Any("5minute", "hour", "day", "month"),
    }
)
@websocket_api.async_response
async def ws_get_statistics_during_period(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle statistics websocket command."""
    start_time_str = msg["start_time"]
    end_time_str = msg.get("end_time")

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start_time")
        return

    if end_time_str:
        if end_time := dt_util.parse_datetime(end_time_str):
            end_time = dt_util.as_utc(end_time)
        else:
            connection.send_error(msg["id"], "invalid_end_time", "Invalid end_time")
            return
    else:
        end_time = None

    connection.send_message(
        await get_instance(hass).async_add_executor_job(
            _ws_get_statistics_during_period,
            hass,
            msg["id"],
            start_time,
            end_time,
            msg.get("statistic_ids"),
            msg.get("period"),
        )
    )


def _ws_get_list_statistic_ids(
    hass: HomeAssistant,
    msg_id: int,
    statistic_type: Literal["mean"] | Literal["sum"] | None = None,
) -> str:
    """Fetch a list of available statistic_id and convert them to json in the executor."""
    return JSON_DUMP(
        messages.result_message(msg_id, list_statistic_ids(hass, None, statistic_type))
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "history/list_statistic_ids",
        vol.Optional("statistic_type"): vol.Any("sum", "mean"),
    }
)
@websocket_api.async_response
async def ws_get_list_statistic_ids(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Fetch a list of available statistic_id."""
    connection.send_message(
        await get_instance(hass).async_add_executor_job(
            _ws_get_list_statistic_ids,
            hass,
            msg["id"],
            msg.get("statistic_type"),
        )
    )


def _ws_get_significant_states(
    hass: HomeAssistant,
    msg_id: int,
    start_time: dt,
    end_time: dt | None = None,
    entity_ids: list[str] | None = None,
    filters: Any | None = None,
    include_start_time_state: bool = True,
    significant_changes_only: bool = True,
    minimal_response: bool = False,
    no_attributes: bool = False,
) -> str:
    """Fetch history significant_states and convert them to json in the executor."""
    return JSON_DUMP(
        messages.result_message(
            msg_id,
            history.get_significant_states(
                hass,
                start_time,
                end_time,
                entity_ids,
                filters,
                include_start_time_state,
                significant_changes_only,
                minimal_response,
                no_attributes,
                True,
            ),
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "history/history_during_period",
        vol.Required("start_time"): str,
        vol.Optional("end_time"): str,
        vol.Optional("entity_ids"): [str],
        vol.Optional("include_start_time_state", default=True): bool,
        vol.Optional("significant_changes_only", default=True): bool,
        vol.Optional("minimal_response", default=False): bool,
        vol.Optional("no_attributes", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_get_history_during_period(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle history during period websocket command."""
    start_time_str = msg["start_time"]
    end_time_str = msg.get("end_time")

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start_time")
        return

    if end_time_str:
        if end_time := dt_util.parse_datetime(end_time_str):
            end_time = dt_util.as_utc(end_time)
        else:
            connection.send_error(msg["id"], "invalid_end_time", "Invalid end_time")
            return
    else:
        end_time = None

    if start_time > dt_util.utcnow():
        connection.send_result(msg["id"], {})
        return

    entity_ids = msg.get("entity_ids")
    include_start_time_state = msg["include_start_time_state"]

    if (
        not include_start_time_state
        and entity_ids
        and not _entities_may_have_state_changes_after(hass, entity_ids, start_time)
    ):
        connection.send_result(msg["id"], {})
        return

    significant_changes_only = msg["significant_changes_only"]
    no_attributes = msg["no_attributes"]
    minimal_response = msg["minimal_response"]

    connection.send_message(
        await get_instance(hass).async_add_executor_job(
            _ws_get_significant_states,
            hass,
            msg["id"],
            start_time,
            end_time,
            entity_ids,
            hass.data[HISTORY_FILTERS],
            include_start_time_state,
            significant_changes_only,
            minimal_response,
            no_attributes,
        )
    )


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
            and not _entities_may_have_state_changes_after(hass, entity_ids, start_time)
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
            _LOGGER.debug("Extracted %d states in %fs", sum(map(len, states)), elapsed)

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


def sqlalchemy_filter_from_include_exclude_conf(conf: ConfigType) -> Filters | None:
    """Build a sql filter from config."""
    filters = Filters()
    if exclude := conf.get(CONF_EXCLUDE):
        filters.excluded_entities = exclude.get(CONF_ENTITIES, [])
        filters.excluded_domains = exclude.get(CONF_DOMAINS, [])
        filters.excluded_entity_globs = exclude.get(CONF_ENTITY_GLOBS, [])
    if include := conf.get(CONF_INCLUDE):
        filters.included_entities = include.get(CONF_ENTITIES, [])
        filters.included_domains = include.get(CONF_DOMAINS, [])
        filters.included_entity_globs = include.get(CONF_ENTITY_GLOBS, [])

    return filters if filters.has_config else None


class Filters:
    """Container for the configured include and exclude filters."""

    def __init__(self) -> None:
        """Initialise the include and exclude filters."""
        self.excluded_entities: list[str] = []
        self.excluded_domains: list[str] = []
        self.excluded_entity_globs: list[str] = []

        self.included_entities: list[str] = []
        self.included_domains: list[str] = []
        self.included_entity_globs: list[str] = []

    def apply(self, query: Query) -> Query:
        """Apply the entity filter."""
        if not self.has_config:
            return query

        return query.filter(self.entity_filter())

    @property
    def has_config(self) -> bool:
        """Determine if there is any filter configuration."""
        return bool(
            self.excluded_entities
            or self.excluded_domains
            or self.excluded_entity_globs
            or self.included_entities
            or self.included_domains
            or self.included_entity_globs
        )

    def bake(self, baked_query: BakedQuery) -> None:
        """Update a baked query.

        Works the same as apply on a baked_query.
        """
        if not self.has_config:
            return

        baked_query += lambda q: q.filter(self.entity_filter())

    def entity_filter(self) -> Any:
        """Generate the entity filter query."""
        includes = []
        if self.included_domains:
            includes.append(
                or_(
                    *[
                        history_models.States.entity_id.like(f"{domain}.%")
                        for domain in self.included_domains
                    ]
                ).self_group()
            )
        if self.included_entities:
            includes.append(history_models.States.entity_id.in_(self.included_entities))
        for glob in self.included_entity_globs:
            includes.append(_glob_to_like(glob))

        excludes = []
        if self.excluded_domains:
            excludes.append(
                or_(
                    *[
                        history_models.States.entity_id.like(f"{domain}.%")
                        for domain in self.excluded_domains
                    ]
                ).self_group()
            )
        if self.excluded_entities:
            excludes.append(history_models.States.entity_id.in_(self.excluded_entities))
        for glob in self.excluded_entity_globs:
            excludes.append(_glob_to_like(glob))

        if not includes and not excludes:
            return None

        if includes and not excludes:
            return or_(*includes)

        if not includes and excludes:
            return not_(or_(*excludes))

        return or_(*includes) & not_(or_(*excludes))


def _glob_to_like(glob_str: str) -> Any:
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
