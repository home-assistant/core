"""Support for Azure Event Hubs."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime
import json
import logging
from typing import Any

from azure.eventhub import EventData, EventDataBatch
from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util.dt import utcnow

from .client import AzureEventHubClient
from .const import (
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DATA_FILTER,
    DOMAIN,
    NON_SEND_STATES,
)

_LOGGER = logging.getLogger(__name__)


class AzureEventHub:
    """A event handler class for Azure Event Hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the listener."""
        self._hass = hass
        self._entry = entry

        self._send_interval: int = self._entry.options[CONF_SEND_INTERVAL]
        self._max_delay: int = self._entry.options[CONF_MAX_DELAY]
        self._entities_filter: vol.Schema = self._hass.data[DOMAIN][DATA_FILTER]

        self._client_config = AzureEventHubClient.from_input(**self._entry.data)

        self._queue: asyncio.PriorityQueue[  # pylint: disable=unsubscriptable-object
            tuple[int, tuple[datetime, Event | None]]
        ] = asyncio.PriorityQueue()

        self._stop = False

        self._listener_remover: Callable[[], None] | None = None
        self._next_send_remover: Callable[[], None] | None = None

    def update_options(self, options: Mapping[str, Any]) -> None:
        """Update the options."""
        self._send_interval = options[CONF_SEND_INTERVAL]
        self._max_delay = options[CONF_MAX_DELAY]

    async def async_test_connection(self) -> None:
        """Test the connection to the event hub."""
        await self._client_config.test_connection()

    async def async_start(self) -> bool:
        """Start the hub.

        This also suppresses the INFO and below logging on the underlying packages, they are very verbose, even at INFO.

        Finally, add listener and schedule the first send, after that each send will schedule the next after the interval.
        """
        logging.getLogger("uamqp").setLevel(logging.WARNING)
        logging.getLogger("azure.eventhub").setLevel(logging.WARNING)

        self._listener_remover = self._hass.bus.async_listen(
            MATCH_ALL, self._async_listen
        )
        self._next_send_remover = async_call_later(
            self._hass, self._send_interval, self._async_send
        )
        return True

    async def async_stop(self) -> bool:
        """Stop the AEH sending by cancelling listereners, queueing None and calling send."""
        if self._next_send_remover:
            self._next_send_remover()
        if self._listener_remover:
            self._listener_remover()
        await self._queue.put((3, (utcnow(), None)))
        await self._async_send(None)
        return True

    async def _async_listen(self, event: Event) -> None:
        """Listen for new messages on the bus and queue them for AEH."""
        await self._queue.put((2, (event.time_fired, event)))

    async def _async_send(self, _) -> None:
        """Send events to eventhub."""
        async with self._client_config.client as client:
            while not self._queue.empty():
                event_batch = await self._fill_batch(client)
                try:
                    await client.send_batch(event_batch)
                except EventHubError as exc:
                    _LOGGER.error("Error in sending events to Event Hub: %s", exc)

        if not self._stop:
            self._next_send_remover = async_call_later(
                self._hass, self._send_interval, self._async_send
            )

    async def _fill_batch(self, client) -> EventDataBatch:
        """Return a batch of events formatted for writing.

        Uses get_nowait instead of await get, because the functions batches and shouldn't wait for new events, then the send function is called.

        Throws ValueError on add to batch when the EventDataBatch object reaches max_size. Put the item back in the queue and the next batch will include it.
        """
        event_batch = await client.create_batch()
        dequeue_count = 0
        dropped = 0
        while True:
            try:
                _, (_, event) = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            dequeue_count += 1

            if event is None:
                self._stop = True
                break

            if not self._on_time(event.time_fired):
                dropped += 1
                continue
            if not (event_data := self._event_to_filtered_event_data(event)):
                continue

            try:
                event_batch.add(event_data)
            except ValueError:
                # batch is full, put the item back in the queue
                await self._queue.put((1, (event.time_fired, event)))
                break

        if dropped > 0:
            _LOGGER.warning(
                "Dropped %d old events, consider increasing the max delay", dropped
            )

        _LOGGER.debug(
            "Sending %d event(s), out of %d dequeued events",
            len(event_batch),
            dequeue_count,
        )
        for _ in range(dequeue_count):
            self._queue.task_done()
        return event_batch

    def _on_time(self, timestamp: datetime) -> bool:
        """Return True if the event is on time, False if it is too old."""
        return (utcnow() - timestamp).seconds <= self._max_delay + self._send_interval

    def _event_to_filtered_event_data(self, event: Event) -> EventData | None:
        """Filter event states and create EventData object."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in NON_SEND_STATES
            or not self._entities_filter(state.entity_id)
        ):
            return None
        return EventData(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8"))
