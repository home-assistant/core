"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, MutableMapping
from dataclasses import dataclass
from datetime import datetime as dt, timedelta
from http import HTTPStatus
import logging
import time
from typing import Any, cast

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
from homeassistant.components.websocket_api import messages
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.const import (
    COMPRESSED_STATE_ATTRIBUTES,
    COMPRESSED_STATE_LAST_CHANGED,
    COMPRESSED_STATE_LAST_UPDATED,
    COMPRESSED_STATE_STATE,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    State,
    callback,
    is_callback,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    EntityFilter,
    convert_include_exclude_filter,
)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.json import JSON_DUMP
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "history"
HISTORY_FILTERS = "history_filters"
HISTORY_ENTITIES_FILTER = "history_entities_filter"
HISTORY_USE_INCLUDE_ORDER = "history_use_include_order"
EVENT_COALESCE_TIME = 0.35

CONF_ORDER = "use_include_order"
MAX_PENDING_HISTORY_STATES = 1024

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
            {vol.Optional(CONF_ORDER, default=False): cv.boolean}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class HistoryLiveStream:
    """Track a history live stream."""

    stream_queue: asyncio.Queue[Event]
    subscriptions: list[CALLBACK_TYPE]
    end_time_unsub: CALLBACK_TYPE | None = None
    task: asyncio.Task | None = None
    wait_sync_task: asyncio.Task | None = None


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


def _ws_get_significant_states(
    hass: HomeAssistant,
    msg_id: int,
    start_time: dt,
    end_time: dt | None,
    entity_ids: list[str] | None,
    filters: Filters | None,
    use_include_order: bool | None,
    include_start_time_state: bool,
    significant_changes_only: bool,
    minimal_response: bool,
    no_attributes: bool,
) -> str:
    """Fetch history significant_states and convert them to json in the executor."""
    states = history.get_significant_states(
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
    )

    if not use_include_order or not filters:
        return JSON_DUMP(messages.result_message(msg_id, states))

    return JSON_DUMP(
        messages.result_message(
            msg_id,
            {
                order_entity: states.pop(order_entity)
                for order_entity in filters.included_entities
                if order_entity in states
            }
            | states,
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
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
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
    no_attributes = msg["no_attributes"]

    if (
        not include_start_time_state
        and entity_ids
        and not _entities_may_have_state_changes_after(
            hass, entity_ids, start_time, no_attributes
        )
    ):
        connection.send_result(msg["id"], {})
        return

    significant_changes_only = msg["significant_changes_only"]
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
            hass.data[HISTORY_USE_INCLUDE_ORDER],
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
            and not _entities_may_have_state_changes_after(
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


def _entities_may_have_state_changes_after(
    hass: HomeAssistant, entity_ids: Iterable, start_time: dt, no_attributes: bool
) -> bool:
    """Check the state machine to see if entities have changed since start time."""
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            return True

        state_time = state.last_changed if no_attributes else state.last_updated
        if state_time > start_time:
            return True

    return False


def _generate_stream_message(
    states: MutableMapping[str, list[dict[str, Any]]],
    start_day: dt,
    end_day: dt,
) -> dict[str, Any]:
    """Generate a history stream message response."""
    return {
        "states": states,
        "start_time": dt_util.utc_to_timestamp(start_day),
        "end_time": dt_util.utc_to_timestamp(end_day),
    }


@callback
def _async_send_empty_response(
    connection: ActiveConnection, msg_id: int, start_time: dt, end_time: dt | None
) -> None:
    """Send an empty response.

    The current case for this is when they ask for entity_ids
    that will all be filtered away because they have UOMs or
    state_class.
    """
    connection.send_result(msg_id)
    stream_end_time = end_time or dt_util.utcnow()
    _async_send_response(connection, msg_id, start_time, stream_end_time, {})


@callback
def _async_send_response(
    connection: ActiveConnection,
    msg_id: int,
    start_time: dt,
    end_time: dt,
    states: MutableMapping[str, list[dict[str, Any]]],
) -> None:
    """Send a response."""
    empty_stream_message = _generate_stream_message(states, start_time, end_time)
    empty_response = messages.event_message(msg_id, empty_stream_message)
    connection.send_message(JSON_DUMP(empty_response))


async def _async_send_historical_states(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg_id: int,
    start_time: dt,
    end_time: dt,
    entity_ids: list[str] | None,
    filters: Filters | None,
    include_start_time_state: bool,
    significant_changes_only: bool,
    minimal_response: bool,
    no_attributes: bool,
    send_empty: bool,
) -> dt | None:
    """Fetch history significant_states and convert them to json in the executor."""
    states = cast(
        MutableMapping[str, list[dict[str, Any]]],
        await hass.async_add_executor_job(
            history.get_significant_states,
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
    last_time = 0

    for state_list in states.values():
        if (
            state_list
            and (state_last_time := state_list[-1][COMPRESSED_STATE_LAST_UPDATED])
            > last_time
        ):
            last_time = state_last_time

    if last_time == 0:
        # If we did not send any states ever, we need to send an empty response
        # so the websocket client knows it should render/process/consume the
        # data.
        if not send_empty:
            return None
        last_time_dt = end_time
    else:
        last_time_dt = dt_util.utc_from_timestamp(last_time)
    _async_send_response(connection, msg_id, start_time, last_time_dt, states)
    return last_time_dt if last_time != 0 else None


def _history_compressed_state(state: State, no_attributes: bool) -> dict[str, Any]:
    """Convert a state to a compressed state."""
    comp_state: dict[str, Any] = {COMPRESSED_STATE_STATE: state.state}
    if not no_attributes or state.domain in history.NEED_ATTRIBUTE_DOMAINS:
        comp_state[COMPRESSED_STATE_ATTRIBUTES] = state.attributes
    comp_state[COMPRESSED_STATE_LAST_UPDATED] = dt_util.utc_to_timestamp(
        state.last_updated
    )
    if state.last_changed != state.last_updated:
        comp_state[COMPRESSED_STATE_LAST_CHANGED] = dt_util.utc_to_timestamp(
            state.last_changed
        )
    return comp_state


def _events_to_compressed_states(
    events: Iterable[Event], no_attributes: bool
) -> MutableMapping[str, list[dict[str, Any]]]:
    """Convert events to a compressed states."""
    states_by_entity_ids: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        state: State = event.data["new_state"]
        entity_id: str = state.entity_id
        states_by_entity_ids.setdefault(entity_id, []).append(
            _history_compressed_state(state, no_attributes)
        )
    return states_by_entity_ids


async def _async_events_consumer(
    subscriptions_setup_complete_time: dt,
    connection: ActiveConnection,
    msg_id: int,
    stream_queue: asyncio.Queue[Event],
    no_attributes: bool,
) -> None:
    """Stream events from the queue."""
    while True:
        events: list[Event] = [await stream_queue.get()]
        # If the event is older than the last db
        # event we already sent it so we skip it.
        if events[0].time_fired <= subscriptions_setup_complete_time:
            continue
        # We sleep for the EVENT_COALESCE_TIME so
        # we can group events together to minimize
        # the number of websocket messages when the
        # system is overloaded with an event storm
        await asyncio.sleep(EVENT_COALESCE_TIME)
        while not stream_queue.empty():
            events.append(stream_queue.get_nowait())

        if history_states := _events_to_compressed_states(events, no_attributes):
            connection.send_message(
                JSON_DUMP(
                    messages.event_message(
                        msg_id,
                        {"states": history_states},
                    )
                )
            )


@callback
def _async_subscribe_events(
    hass: HomeAssistant,
    subscriptions: list[CALLBACK_TYPE],
    target: Callable[[Event], None],
    entities_filter: EntityFilter | None,
    entity_ids: list[str] | None,
    significant_changes_only: bool,
    minimal_response: bool,
) -> None:
    """Subscribe to events for the entities and devices or all.

    These are the events we need to listen for to do
    the live history stream.
    """
    assert is_callback(target), "target must be a callback"

    @callback
    def _forward_state_events_filtered(event: Event) -> None:
        """Filter state events and forward them."""
        if (new_state := event.data.get("new_state")) is None or (
            old_state := event.data.get("old_state")
        ) is None:
            return
        assert isinstance(new_state, State)
        assert isinstance(old_state, State)
        if (entities_filter and not entities_filter(new_state.entity_id)) or (
            (significant_changes_only or minimal_response)
            and new_state.state == old_state.state
            and new_state.domain not in history.SIGNIFICANT_DOMAINS
        ):
            return
        target(event)

    if entity_ids:
        subscriptions.append(
            async_track_state_change_event(
                hass, entity_ids, _forward_state_events_filtered
            )
        )
        return

    # We want the firehose
    subscriptions.append(
        hass.bus.async_listen(
            EVENT_STATE_CHANGED,
            _forward_state_events_filtered,
            run_immediately=True,
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "history/stream",
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
async def ws_stream(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle history stream websocket command."""
    start_time_str = msg["start_time"]
    msg_id: int = msg["id"]
    entity_ids: list[str] | None = msg.get("entity_ids")
    utc_now = dt_util.utcnow()
    filters: Filters | None = None
    entities_filter: EntityFilter | None = None
    if not entity_ids:
        filters = hass.data[HISTORY_FILTERS]
        entities_filter = hass.data[HISTORY_ENTITIES_FILTER]

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)

    if not start_time or start_time > utc_now:
        connection.send_error(msg_id, "invalid_start_time", "Invalid start_time")
        return

    end_time_str = msg.get("end_time")
    end_time: dt | None = None
    if end_time_str:
        if not (end_time := dt_util.parse_datetime(end_time_str)):
            connection.send_error(msg_id, "invalid_end_time", "Invalid end_time")
            return
        end_time = dt_util.as_utc(end_time)
        if end_time < start_time:
            connection.send_error(msg_id, "invalid_end_time", "Invalid end_time")
            return

    entity_ids = msg.get("entity_ids")
    include_start_time_state = msg["include_start_time_state"]
    significant_changes_only = msg["significant_changes_only"]
    no_attributes = msg["no_attributes"]
    minimal_response = msg["minimal_response"]

    if end_time and end_time <= utc_now:
        if (
            not include_start_time_state
            and entity_ids
            and not _entities_may_have_state_changes_after(
                hass, entity_ids, start_time, no_attributes
            )
        ):
            _async_send_empty_response(connection, msg_id, start_time, end_time)
            return

        connection.subscriptions[msg_id] = callback(lambda: None)
        connection.send_result(msg_id)
        await _async_send_historical_states(
            hass,
            connection,
            msg_id,
            start_time,
            end_time,
            entity_ids,
            filters,
            include_start_time_state,
            significant_changes_only,
            minimal_response,
            no_attributes,
            True,
        )
        return

    subscriptions: list[CALLBACK_TYPE] = []
    stream_queue: asyncio.Queue[Event] = asyncio.Queue(MAX_PENDING_HISTORY_STATES)
    live_stream = HistoryLiveStream(
        subscriptions=subscriptions, stream_queue=stream_queue
    )

    @callback
    def _unsub(*_utc_time: Any) -> None:
        """Unsubscribe from all events."""
        for subscription in subscriptions:
            subscription()
        subscriptions.clear()
        if live_stream.task:
            live_stream.task.cancel()
        if live_stream.wait_sync_task:
            live_stream.wait_sync_task.cancel()
        if live_stream.end_time_unsub:
            live_stream.end_time_unsub()
            live_stream.end_time_unsub = None

    if end_time:
        live_stream.end_time_unsub = async_track_point_in_utc_time(
            hass, _unsub, end_time
        )

    @callback
    def _queue_or_cancel(event: Event) -> None:
        """Queue an event to be processed or cancel."""
        try:
            stream_queue.put_nowait(event)
        except asyncio.QueueFull:
            _LOGGER.debug(
                "Client exceeded max pending messages of %s",
                MAX_PENDING_HISTORY_STATES,
            )
            _unsub()

    _async_subscribe_events(
        hass,
        subscriptions,
        _queue_or_cancel,
        entities_filter,
        entity_ids,
        significant_changes_only=significant_changes_only,
        minimal_response=minimal_response,
    )
    subscriptions_setup_complete_time = dt_util.utcnow()
    connection.subscriptions[msg_id] = _unsub
    connection.send_result(msg_id)
    # Fetch everything from history
    last_event_time = await _async_send_historical_states(
        hass,
        connection,
        msg_id,
        start_time,
        subscriptions_setup_complete_time,
        entity_ids,
        filters,
        include_start_time_state,
        significant_changes_only,
        minimal_response,
        no_attributes,
        True,
    )

    live_stream.task = asyncio.create_task(
        _async_events_consumer(
            subscriptions_setup_complete_time,
            connection,
            msg_id,
            stream_queue,
            no_attributes,
        )
    )

    if msg_id not in connection.subscriptions:
        # Unsubscribe happened while sending historical states
        return

    live_stream.wait_sync_task = asyncio.create_task(
        get_instance(hass).async_block_till_done()
    )
    await live_stream.wait_sync_task

    #
    # Fetch any states from the database that have
    # not been committed since the original fetch
    # so we can switch over to using the subscriptions
    #
    # We only want states that happened after the last state
    # we had from the last database query
    #
    await _async_send_historical_states(
        hass,
        connection,
        msg_id,
        last_event_time or start_time,
        subscriptions_setup_complete_time,
        entity_ids,
        filters,
        False,  # We don't want the start time state again
        significant_changes_only,
        minimal_response,
        no_attributes,
        send_empty=not last_event_time,
    )
