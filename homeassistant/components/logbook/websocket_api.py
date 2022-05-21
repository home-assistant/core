"""Event parser and human readable log generator."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime as dt
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.recorder import get_instance
from homeassistant.components.websocket_api import messages
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import JSON_DUMP
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, EVENT_STATE_CHANGED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.util.dt as dt_util

from .helpers import (
    async_determine_event_types,
    async_filter_entities,
    is_state_filtered,
)
from .models import async_event_to_row
from .processor import EventProcessor

MAX_PENDING_LOGBOOK_EVENTS = 2048
EVENT_COALESCE_TIME = 1

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the logbook websocket API."""
    websocket_api.async_register_command(hass, ws_get_events)
    websocket_api.async_register_command(hass, ws_event_stream)


def _ws_formatted_get_events(
    msg_id: int,
    start_day: dt,
    end_day: dt,
    formatter: Callable[[int, Any], dict[str, Any]],
    event_processor: EventProcessor,
) -> tuple[str, dt | None]:
    """Fetch events and convert them to json in the executor."""
    events = event_processor.get_events(start_day, end_day)
    last_time = None
    if events:
        last_time = dt_util.utc_from_timestamp(events[-1]["when"])
    result = formatter(msg_id, events)
    return JSON_DUMP(result), last_time


async def async_stream_events(
    connection: ActiveConnection,
    msg_id: int,
    stream_queue: asyncio.Queue[Event],
    event_processor: EventProcessor,
    last_time_from_db: dt,
) -> None:
    """Stream events from the queue."""
    event_processor.switch_to_live()

    while True:
        events: list[Event] = [await stream_queue.get()]
        # If the event is older than the last db
        # event we already sent it so we skip it.
        if events[0].time_fired <= last_time_from_db:
            stream_queue.task_done()
            continue
        await asyncio.sleep(EVENT_COALESCE_TIME)  # try to group events
        while True:
            try:
                events.append(stream_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if logbook_events := event_processor.humanify(
            row for row in (async_event_to_row(e) for e in events) if row is not None
        ):
            connection.send_message(
                JSON_DUMP(
                    messages.event_message(
                        msg_id,
                        logbook_events,
                    )
                )
            )
        stream_queue.task_done()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "logbook/event_stream",
        vol.Required("start_time"): str,
        vol.Optional("entity_ids"): [str],
        vol.Optional("device_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_event_stream(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle logbook get events websocket command."""
    start_time_str = msg["start_time"]
    utc_now = dt_util.utcnow()

    if start_time := dt_util.parse_datetime(start_time_str):
        start_time = dt_util.as_utc(start_time)

    if not start_time or start_time > utc_now:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start_time")
        return

    device_ids = msg.get("device_ids")
    entity_ids = msg.get("entity_ids")
    if entity_ids:
        entity_ids = async_filter_entities(hass, entity_ids)
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

    stream_queue: asyncio.Queue[Event] = asyncio.Queue(MAX_PENDING_LOGBOOK_EVENTS)
    task: asyncio.Task
    subscriptions: list[CALLBACK_TYPE] = []

    def _unsub() -> None:
        """Unsubscribe from all events."""
        for subscription in subscriptions:
            subscription()
        task.cancel()

    @callback
    def _queue_or_cancel(event: Event) -> None:
        """Queue an event to be processed or cancel."""
        nonlocal task
        try:
            stream_queue.put_nowait(event)
        except asyncio.QueueFull:
            _LOGGER.debug(
                "Client exceeded max pending messages of %s (likely disconnected without unsubscribe)",
                MAX_PENDING_LOGBOOK_EVENTS,
            )
            _unsub()

    ent_reg = er.async_get(hass)
    if entity_ids or device_ids:
        entity_ids_set = set(entity_ids) if entity_ids else set()
        device_ids_set = set(device_ids) if device_ids else set()

        @callback
        def _forward_events_filtered(event: Event) -> None:
            event_data = event.data
            if (
                entity_ids_set and event_data.get(ATTR_ENTITY_ID) in entity_ids_set
            ) or (device_ids_set and event_data.get(ATTR_DEVICE_ID) in device_ids_set):
                _queue_or_cancel(event)

        event_forwarder = _forward_events_filtered
    else:

        @callback
        def _forward_events(event: Event) -> None:
            _queue_or_cancel(event)

        event_forwarder = _forward_events

    for event_type in event_types:
        subscriptions.append(
            hass.bus.async_listen(event_type, event_forwarder, run_immediately=True)
        )

    @callback
    def _forward_state_events_filtered(event: Event) -> None:
        if event.data.get("old_state") is None or event.data.get("new_state") is None:
            return
        state: State = event.data["new_state"]
        if not is_state_filtered(ent_reg, state):
            _queue_or_cancel(event)

    if entity_ids:
        subscriptions.append(
            async_track_state_change_event(
                hass, entity_ids, _forward_state_events_filtered
            )
        )
    else:
        # We want the firehose
        subscriptions.append(
            hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _forward_state_events_filtered,
                run_immediately=True,
            )
        )

    message, last_time = await get_instance(hass).async_add_executor_job(
        _ws_formatted_get_events,
        msg["id"],
        start_time,
        utc_now,
        messages.event_message,
        event_processor,
    )
    task = asyncio.create_task(
        async_stream_events(
            connection,
            msg["id"],
            stream_queue,
            event_processor,
            last_time or start_time,
        )
    )

    connection.subscriptions[msg["id"]] = _unsub
    connection.send_result(msg["id"])
    connection.send_message(message)


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

    message, _ = await get_instance(hass).async_add_executor_job(
        _ws_formatted_get_events,
        msg["id"],
        start_time,
        end_time,
        messages.result_message,
        event_processor,
    )
    connection.send_message(message)
