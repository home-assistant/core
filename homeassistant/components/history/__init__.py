"""Provide pre-made queries on top of the recorder component."""

import asyncio
from collections.abc import Callable
from datetime import datetime as dt, timedelta
from http import HTTPStatus
from typing import NamedTuple

from aiohttp import web
import voluptuous as vol

from homeassistant.auth.permissions import filter_entity_ids_by_permission
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import frontend
from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView
from homeassistant.components.recorder import get_instance, history
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import CONF_EXCLUDE, CONF_INCLUDE, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entityfilter import INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA
from homeassistant.helpers.http import MIN_COMPRESSED_RESPONSE_SIZE
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from . import websocket_api
from .const import DOMAIN
from .helpers import entities_may_have_state_changes_after, has_states_before

CONF_ORDER = "use_include_order"

_ONE_DAY = timedelta(days=1)


class _HistoryQueryKey(NamedTuple):
    """Identify a history query whose result can be shared."""

    start_time: dt
    end_time: dt
    entity_ids: tuple[str, ...]
    include_start_time_state: bool
    significant_changes_only: bool
    minimal_response: bool
    no_attributes: bool


_IN_FLIGHT_HISTORY_QUERIES: HassKey[dict[_HistoryQueryKey, asyncio.Future[bytes]]] = (
    HassKey("history_in_flight_period_queries")
)

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
    """Set up the history hooks."""
    hass.http.register_view(HistoryPeriodView())
    frontend.async_register_built_in_panel(hass, "history", "history", "mdi:chart-box")
    websocket_api.async_setup(hass)
    return True


async def _async_get_or_create_history_result(
    hass: HomeAssistant,
    query_key: _HistoryQueryKey,
    create_result_future: Callable[[], asyncio.Future[bytes]],
) -> bytes:
    """Get an in-flight history result or start a new query."""
    in_flight_queries = hass.data.setdefault(_IN_FLIGHT_HISTORY_QUERIES, {})
    if (
        result_future := in_flight_queries.get(query_key)
    ) is None or result_future.done():
        result_future = create_result_future()
        in_flight_queries[query_key] = result_future

        def remove_completed_query(future: asyncio.Future[bytes]) -> None:
            if in_flight_queries.get(query_key) is future:
                del in_flight_queries[query_key]
            if not future.cancelled():
                future.exception()

        result_future.add_done_callback(remove_completed_query)

    # A disconnected requester must not cancel a query used by other requesters.
    return await asyncio.shield(result_future)


class HistoryPeriodView(HomeAssistantView):
    """Handle history period requests."""

    url = "/api/history/period"
    name = "api:history:view-period"
    extra_urls = ["/api/history/period/{datetime}"]

    async def get(
        self, request: web.Request, datetime: str | None = None
    ) -> web.Response:
        """Return history over a period of time."""
        datetime_ = None
        query = request.query

        if datetime and (datetime_ := dt_util.parse_datetime(datetime)) is None:
            return self.json_message("Invalid datetime", HTTPStatus.BAD_REQUEST)

        if not (entity_ids_str := query.get("filter_entity_id")) or not (
            entity_ids := entity_ids_str.strip().lower().split(",")
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

        entity_ids = filter_entity_ids_by_permission(
            request[KEY_HASS_USER], entity_ids, POLICY_READ
        )
        if not entity_ids:
            return self.json([])

        now = dt_util.utcnow()
        if datetime_:
            start_time = dt_util.as_utc(datetime_)
        else:
            start_time = now - _ONE_DAY

        if start_time > now:
            return self.json([])

        if end_time_str := query.get("end_time"):
            if end_time := dt_util.parse_datetime(end_time_str):
                end_time = dt_util.as_utc(end_time)
            else:
                return self.json_message("Invalid end_time", HTTPStatus.BAD_REQUEST)
        else:
            end_time = start_time + _ONE_DAY

        include_start_time_state = "skip_initial_state" not in query
        significant_changes_only = query.get("significant_changes_only", "1") != "0"

        minimal_response = "minimal_response" in request.query
        no_attributes = "no_attributes" in request.query

        if (
            # has_states_before will return True if there are states older than
            # end_time. If it's false, we know there are no states in the
            # database up until end_time.
            (end_time and not has_states_before(hass, end_time))
            or (
                not include_start_time_state
                and entity_ids
                and not entities_may_have_state_changes_after(
                    hass, entity_ids, start_time, no_attributes
                )
            )
        ):
            return self.json([])

        # Permissions have already been applied, so matching authorized queries
        # can share their result even when they originate from different users.
        query_key = _HistoryQueryKey(
            start_time=start_time,
            end_time=end_time,
            entity_ids=tuple(entity_ids),
            include_start_time_state=include_start_time_state,
            significant_changes_only=significant_changes_only,
            minimal_response=minimal_response,
            no_attributes=no_attributes,
        )
        body = await _async_get_or_create_history_result(
            hass,
            query_key,
            lambda: get_instance(hass).async_add_executor_job(
                self._sorted_significant_states_json_bytes,
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
        response = web.Response(
            body=body,
            content_type=CONTENT_TYPE_JSON,
            zlib_executor_size=32768,
        )
        if len(body) > MIN_COMPRESSED_RESPONSE_SIZE:
            response.enable_compression()
        return response

    def _sorted_significant_states_json_bytes(
        self,
        hass: HomeAssistant,
        start_time: dt,
        end_time: dt,
        entity_ids: list[str],
        include_start_time_state: bool,
        significant_changes_only: bool,
        minimal_response: bool,
        no_attributes: bool,
    ) -> bytes:
        """Fetch significant stats from the database as json."""
        with session_scope(hass=hass, read_only=True) as session:
            return json_bytes(
                list(
                    history.get_significant_states_with_session(
                        hass,
                        session,
                        start_time,
                        end_time,
                        entity_ids,
                        None,
                        include_start_time_state,
                        significant_changes_only,
                        minimal_response,
                        no_attributes,
                    ).values()
                )
            )
