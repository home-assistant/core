"""Event parser and human readable log generator."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime as dt, timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.recorder import get_instance
from homeassistant.components.websocket_api import messages
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.entityfilter import EntityFilter
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.json import JSON_DUMP
import homeassistant.util.dt as dt_util

from .const import LOGBOOK_ENTITIES_FILTER
from .helpers import (
    async_determine_event_types,
    async_filter_entities,
    async_subscribe_events,
)
from .models import async_event_to_row
from .processor import EventProcessor

MAX_PENDING_LOGBOOK_EVENTS = 2048
EVENT_COALESCE_TIME = 0.35
MAX_RECORDER_WAIT = 10
# minimum size that we will split the query
BIG_QUERY_HOURS = 25
# how many hours to deliver in the first chunk when we split the query
BIG_QUERY_RECENT_HOURS = 24

_LOGGER = logging.getLogger(__name__)


@dataclass
class LogbookLiveStream:
    """Track a logbook live stream."""

    stream_queue: asyncio.Queue[Event]
    subscriptions: list[CALLBACK_TYPE]
    end_time_unsub: CALLBACK_TYPE | None = None
    task: asyncio.Task | None = None


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the logbook websocket API."""
    websocket_api.async_register_command(hass, ws_get_events)
    websocket_api.async_register_command(hass, ws_event_stream)


async def _async_wait_for_recorder_sync(hass: HomeAssistant) -> None:
    """Wait for the recorder to sync."""
    try:
        await asyncio.wait_for(
            get_instance(hass).async_block_till_done(), MAX_RECORDER_WAIT
        )
    except asyncio.TimeoutError:
        _LOGGER.debug(
            "Recorder is behind more than %s seconds, starting live stream; Some results may be missing"
        )


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
    empty_stream_message = _generate_stream_message([], start_time, stream_end_time)
    empty_response = messages.event_message(msg_id, empty_stream_message)
    connection.send_message(JSON_DUMP(empty_response))


async def _async_send_historical_events(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg_id: int,
    start_time: dt,
    end_time: dt,
    formatter: Callable[[int, Any], dict[str, Any]],
    event_processor: EventProcessor,
    partial: bool,
) -> dt | None:
    """Select historical data from the database and deliver it to the websocket.

    If the query is considered a big query we will split the request into
    two chunks so that they get the recent events first and the select
    that is expected to take a long time comes in after to ensure
    they are not stuck at a loading screen and can start looking at
    the data right away.

    This function returns the time of the most recent event we sent to the
    websocket.
    """
    is_big_query = (
        not event_processor.entity_ids
        and not event_processor.device_ids
        and ((end_time - start_time) > timedelta(hours=BIG_QUERY_HOURS))
    )

    if not is_big_query:
        message, last_event_time = await _async_get_ws_stream_events(
            hass,
            msg_id,
            start_time,
            end_time,
            formatter,
            event_processor,
            partial,
        )
        # If there is no last_event_time, there are no historical
        # results, but we still send an empty message
        # if its the last one (not partial) so
        # consumers of the api know their request was
        # answered but there were no results
        if last_event_time or not partial:
            connection.send_message(message)
        return last_event_time

    # This is a big query so we deliver
    # the first three hours and then
    # we fetch the old data
    recent_query_start = end_time - timedelta(hours=BIG_QUERY_RECENT_HOURS)
    recent_message, recent_query_last_event_time = await _async_get_ws_stream_events(
        hass,
        msg_id,
        recent_query_start,
        end_time,
        formatter,
        event_processor,
        partial=True,
    )
    if recent_query_last_event_time:
        connection.send_message(recent_message)

    older_message, older_query_last_event_time = await _async_get_ws_stream_events(
        hass,
        msg_id,
        start_time,
        recent_query_start,
        formatter,
        event_processor,
        partial,
    )
    # If there is no last_event_time, there are no historical
    # results, but we still send an empty message
    # if its the last one (not partial) so
    # consumers of the api know their request was
    # answered but there were no results
    if older_query_last_event_time or not partial:
        connection.send_message(older_message)

    # Returns the time of the newest event
    return recent_query_last_event_time or older_query_last_event_time


async def _async_get_ws_stream_events(
    hass: HomeAssistant,
    msg_id: int,
    start_time: dt,
    end_time: dt,
    formatter: Callable[[int, Any], dict[str, Any]],
    event_processor: EventProcessor,
    partial: bool,
) -> tuple[str, dt | None]:
    """Async wrapper around _ws_formatted_get_events."""
    return await get_instance(hass).async_add_executor_job(
        _ws_stream_get_events,
        msg_id,
        start_time,
        end_time,
        formatter,
        event_processor,
        partial,
    )


def _generate_stream_message(
    events: list[dict[str, Any]], start_day: dt, end_day: dt
) -> dict[str, Any]:
    """Generate a logbook stream message response."""
    return {
        "events": events,
        "start_time": dt_util.utc_to_timestamp(start_day),
        "end_time": dt_util.utc_to_timestamp(end_day),
    }


def _ws_stream_get_events(
    msg_id: int,
    start_day: dt,
    end_day: dt,
    formatter: Callable[[int, Any], dict[str, Any]],
    event_processor: EventProcessor,
    partial: bool,
) -> tuple[str, dt | None]:
    """Fetch events and convert them to json in the executor."""
    events = event_processor.get_events(start_day, end_day)
    last_time = None
    if events:
        last_time = dt_util.utc_from_timestamp(events[-1]["when"])
    message = _generate_stream_message(events, start_day, end_day)
    if partial:
        # This is a hint to consumers of the api that
        # we are about to send a another block of historical
        # data in case the UI needs to show that historical
        # data is still loading in the future
        message["partial"] = True
    return JSON_DUMP(formatter(msg_id, message)), last_time


async def _async_events_consumer(
    subscriptions_setup_complete_time: dt,
    connection: ActiveConnection,
    msg_id: int,
    stream_queue: asyncio.Queue[Event],
    event_processor: EventProcessor,
) -> None:
    """Stream events from the queue."""
    event_processor.switch_to_live()

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

        if logbook_events := event_processor.humanify(
            async_event_to_row(e) for e in events
        ):
            connection.send_message(
                JSON_DUMP(
                    messages.event_message(
                        msg_id,
                        {"events": logbook_events},
                    )
                )
            )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "logbook/event_stream",
        vol.Required("start_time"): str,
        vol.Optional("end_time"): str,
        vol.Optional("entity_ids"): [str],
        vol.Optional("device_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_event_stream(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle logbook stream events websocket command."""
    start_time_str = msg["start_time"]
    msg_id: int = msg["id"]
    utc_now = dt_util.utcnow()

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

    device_ids = msg.get("device_ids")
    entity_ids = msg.get("entity_ids")
    if entity_ids:
        entity_ids = async_filter_entities(hass, entity_ids)
        if not entity_ids and not device_ids:
            _async_send_empty_response(connection, msg_id, start_time, end_time)
            return

    event_types = async_determine_event_types(hass, entity_ids, device_ids)
    event_processor = EventProcessor(
        hass,
        event_types,
        entity_ids,
        device_ids,
        None,
        timestamp=True,
        include_entity_name=False,
    )

    if end_time and end_time <= utc_now:
        # Not live stream but we it might be a big query
        connection.subscriptions[msg_id] = callback(lambda: None)
        connection.send_result(msg_id)
        # Fetch everything from history
        await _async_send_historical_events(
            hass,
            connection,
            msg_id,
            start_time,
            end_time,
            messages.event_message,
            event_processor,
            partial=False,
        )
        return

    subscriptions: list[CALLBACK_TYPE] = []
    stream_queue: asyncio.Queue[Event] = asyncio.Queue(MAX_PENDING_LOGBOOK_EVENTS)
    live_stream = LogbookLiveStream(
        subscriptions=subscriptions, stream_queue=stream_queue
    )

    @callback
    def _unsub(*time: Any) -> None:
        """Unsubscribe from all events."""
        for subscription in subscriptions:
            subscription()
        subscriptions.clear()
        if live_stream.task:
            live_stream.task.cancel()
        if live_stream.end_time_unsub:
            live_stream.end_time_unsub()

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
                MAX_PENDING_LOGBOOK_EVENTS,
            )
            _unsub()

    entities_filter: EntityFilter | None = None
    if not event_processor.limited_select:
        entities_filter = hass.data[LOGBOOK_ENTITIES_FILTER]

    async_subscribe_events(
        hass,
        subscriptions,
        _queue_or_cancel,
        event_types,
        entities_filter,
        entity_ids,
        device_ids,
    )
    subscriptions_setup_complete_time = dt_util.utcnow()
    connection.subscriptions[msg_id] = _unsub
    connection.send_result(msg_id)
    # Fetch everything from history
    last_event_time = await _async_send_historical_events(
        hass,
        connection,
        msg_id,
        start_time,
        subscriptions_setup_complete_time,
        messages.event_message,
        event_processor,
        partial=True,
    )

    await _async_wait_for_recorder_sync(hass)
    if msg_id not in connection.subscriptions:
        # Unsubscribe happened while waiting for recorder
        return

    #
    # Fetch any events from the database that have
    # not been committed since the original fetch
    # so we can switch over to using the subscriptions
    #
    # We only want events that happened after the last event
    # we had from the last database query or the maximum
    # time we allow the recorder to be behind
    #
    max_recorder_behind = subscriptions_setup_complete_time - timedelta(
        seconds=MAX_RECORDER_WAIT
    )
    second_fetch_start_time = max(
        last_event_time or max_recorder_behind, max_recorder_behind
    )
    await _async_send_historical_events(
        hass,
        connection,
        msg_id,
        second_fetch_start_time,
        subscriptions_setup_complete_time,
        messages.event_message,
        event_processor,
        partial=False,
    )

    if not subscriptions:
        # Unsubscribe happened while waiting for formatted events
        # or there are no supported entities (all UOM or state class)
        # or devices
        return

    live_stream.task = asyncio.create_task(
        _async_events_consumer(
            subscriptions_setup_complete_time,
            connection,
            msg_id,
            stream_queue,
            event_processor,
        )
    )


def _ws_formatted_get_events(
    msg_id: int,
    start_time: dt,
    end_time: dt,
    event_processor: EventProcessor,
) -> str:
    """Fetch events and convert them to json in the executor."""
    return JSON_DUMP(
        messages.result_message(
            msg_id, event_processor.get_events(start_time, end_time)
        )
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "logbook/get_events",
        vol.Required("start_time"): str,
        vol.Optional("end_time"): str,
        vol.Optional("entity_ids"): [str],
        vol.Optional("device_ids"): [str],
        vol.Optional("context_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_events(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle logbook get events websocket command."""
    start_time_str = msg["start_time"]
    end_time_str = msg.get("end_time")
    utc_now = dt_util.utcnow()

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start_time")
        return

    if not end_time_str:
        end_time = utc_now
    elif parsed_end_time := dt_util.parse_datetime(end_time_str):
        end_time = dt_util.as_utc(parsed_end_time)
    else:
        connection.send_error(msg["id"], "invalid_end_time", "Invalid end_time")
        return

    if start_time > utc_now:
        connection.send_result(msg["id"], [])
        return

    device_ids = msg.get("device_ids")
    entity_ids = msg.get("entity_ids")
    context_id = msg.get("context_id")
    if entity_ids:
        entity_ids = async_filter_entities(hass, entity_ids)
        if not entity_ids and not device_ids:
            # Everything has been filtered away
            connection.send_result(msg["id"], [])
            return

    event_types = async_determine_event_types(hass, entity_ids, device_ids)

    event_processor = EventProcessor(
        hass,
        event_types,
        entity_ids,
        device_ids,
        context_id,
        timestamp=True,
        include_entity_name=False,
    )

    connection.send_message(
        await get_instance(hass).async_add_executor_job(
            _ws_formatted_get_events,
            msg["id"],
            start_time,
            end_time,
            event_processor,
        )
    )
