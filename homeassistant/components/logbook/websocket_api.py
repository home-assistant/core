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
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.util.dt as dt_util

from .event_as_row import async_event_to_row
from .helpers import async_determine_event_types
from .processor import EventProcessor

MAX_PENDING_LOGBOOK_EVENTS = 2048
EVENT_COALESCE_TIME = 1

_LOGGER = logging.getLogger(__name__)


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
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg_id: int,
    stream_queue: asyncio.Queue[Event],
    event_processor: EventProcessor,
    last_time_from_db: dt,
) -> None:
    """Stream events from the queue."""
    instance = get_instance(hass)
    # Fetch any events from the database that have
    # not been committed since the original fetch
    await asyncio.sleep(instance.commit_interval)
    message, last_time = await instance.async_add_executor_job(
        _ws_formatted_get_events,
        msg_id,
        last_time_from_db,
        dt_util.utcnow(),
        messages.event_message,
        event_processor,
    )
    if last_time:
        connection.send_message(message)
    else:
        last_time = last_time_from_db

    event_processor.switch_to_live()

    while True:
        events: list[Event] = [await stream_queue.get()]
        # If the event is older than the last db
        # event we already sent it so we skip it.
        if events[0].time_fired <= last_time:
            continue
        await asyncio.sleep(EVENT_COALESCE_TIME)  # try to group events
        while True:
            try:
                events.append(stream_queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        try:
            logbook_events = event_processor.humanify(
                row
                for row in (async_event_to_row(e) for e in events)
                if row is not None
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.critical("Error processing logbook events: %s", exc_info=True)
            continue

        if not logbook_events:
            continue

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
    else:
        connection.send_error(msg["id"], "invalid_start_time", "Invalid start_time")
        return

    if start_time > utc_now:
        connection.send_result(msg["id"], [])
        return

    device_ids = msg.get("device_ids")
    entity_ids = msg.get("entity_ids")
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
    subscriptions: list[CALLBACK_TYPE] = []

    @callback
    def _forward_events(event: Event) -> None:
        stream_queue.put_nowait(event)

    for event_type in event_types:
        subscriptions.append(
            hass.bus.async_listen(event_type, _forward_events, run_immediately=True)
        )
    if entity_ids:
        subscriptions.append(
            async_track_state_change_event(hass, entity_ids, _forward_events)
        )
    else:
        # We want the firehose
        subscriptions.append(
            hass.bus.async_listen(
                EVENT_STATE_CHANGED, _forward_events, run_immediately=True
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
            hass,
            connection,
            msg["id"],
            stream_queue,
            event_processor,
            last_time or start_time,
        )
    )

    def _unsub() -> None:
        """Unsubscribe from all events."""
        for subscription in subscriptions:
            subscription()
        task.cancel()

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
