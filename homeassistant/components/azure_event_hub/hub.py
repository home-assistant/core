"""Support for Azure Event Hubs."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import time

from azure.eventhub import EventData, EventDataBatch
from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.json import JSONEncoder

from .models import AzureEventHubClient

_LOGGER = logging.getLogger(__name__)


class AzureEventHub:
    """A event handler class for Azure Event Hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_config: AzureEventHubClient,
        entities_filter: vol.Schema,
        send_interval: int,
        max_delay: int,
    ) -> None:
        """Initialize the listener."""
        self.hass = hass
        self._client_config = client_config
        self._entities_filter = entities_filter
        self.send_interval = send_interval
        self.max_delay = max_delay + send_interval

        self.queue: asyncio.PriorityQueue[  # pylint: disable=unsubscriptable-object
            tuple[int, tuple[float, Event | None]]
        ] = asyncio.PriorityQueue()
        self._listener_remover: Callable[[], None] | None = None
        self._next_send_remover: Callable[[], None] | None = None
        self.shutdown = False

    async def async_start(self) -> None:
        """Start the recorder, suppress logging and register the callbacks and do the first send after five seconds, to capture the startup events."""
        # suppress the INFO and below logging on the underlying packages, they are very verbose, even at INFO
        logging.getLogger("uamqp").setLevel(logging.WARNING)
        logging.getLogger("azure.eventhub").setLevel(logging.WARNING)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)
        self._listener_remover = self.hass.bus.async_listen(
            MATCH_ALL, self.async_listen
        )

        # schedule the first send after 10 seconds to capture startup events, after that each send will schedule the next after the interval.
        self._next_send_remover = async_call_later(self.hass, 10, self.async_send)

    async def async_shutdown(self, _: Event | None) -> None:
        """Shut down the AEH by queueing None and calling send."""
        if self._next_send_remover:
            self._next_send_remover()
        if self._listener_remover:
            self._listener_remover()
        await self.queue.put((3, (time.monotonic(), None)))
        await self.async_send(None)

    async def async_listen(self, event: Event) -> None:
        """Listen for new messages on the bus and queue them for AEH."""
        await self.queue.put((2, (time.monotonic(), event)))

    async def async_send(self, _) -> None:
        """Write preprocessed events to eventhub, with retry."""
        async with self._client_config.get_client() as client:
            while not self.queue.empty():
                data_batch, dequeue_count = await self.fill_batch(client)
                _LOGGER.debug(
                    "Sending %d event(s), out of %d events in the queue",
                    len(data_batch),
                    dequeue_count,
                )
                if data_batch:
                    try:
                        await client.send_batch(data_batch)
                    except EventHubError as exc:
                        _LOGGER.error("Error in sending events to Event Hub: %s", exc)
                    finally:
                        for _ in range(dequeue_count):
                            self.queue.task_done()

        if not self.shutdown:
            self._next_send_remover = async_call_later(
                self.hass, self.send_interval, self.async_send
            )

    async def fill_batch(self, client) -> tuple[EventDataBatch, int]:
        """Return a batch of events formatted for writing.

        Uses get_nowait instead of await get, because the functions batches and doesn't wait for each single event, the send function is called.

        Throws ValueError on add to batch when the EventDataBatch object reaches max_size. Put the item back in the queue and the next batch will include it.
        """
        event_batch = await client.create_batch()
        dequeue_count = 0
        dropped = 0
        while not self.shutdown:
            try:
                _, (timestamp, event) = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            dequeue_count += 1
            if not event:
                self.shutdown = True
                break
            event_data = self._event_to_filtered_event_data(event)
            if not event_data:
                continue
            if time.monotonic() - timestamp <= self.max_delay:
                try:
                    event_batch.add(event_data)
                except ValueError:
                    self.queue.put_nowait((1, (timestamp, event)))
                    break
            else:
                dropped += 1

        if dropped:
            _LOGGER.warning(
                "Dropped %d old events, consider increasing the max_delay", dropped
            )

        return event_batch, dequeue_count

    def _event_to_filtered_event_data(self, event: Event) -> EventData | None:
        """Filter event states and create EventData object."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not self._entities_filter(state.entity_id)
        ):
            return None
        return EventData(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8"))
