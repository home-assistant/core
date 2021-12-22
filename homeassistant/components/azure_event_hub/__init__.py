"""Support for Azure Event Hubs."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import time
from typing import Any

from azure.eventhub import EventData, EventDataBatch
from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryNotReady
from homeassistant.const import MATCH_ALL, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType

from .client import AzureEventHubClient
from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_FILTER,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DATA_FILTER,
    DATA_HUB,
    DEFAULT_MAX_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EVENT_HUB_INSTANCE_NAME): cv.string,
                vol.Optional(CONF_EVENT_HUB_CON_STRING): cv.string,
                vol.Optional(CONF_EVENT_HUB_NAMESPACE): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_POLICY): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_KEY): cv.string,
                vol.Optional(CONF_SEND_INTERVAL): cv.positive_int,
                vol.Optional(CONF_MAX_DELAY): cv.positive_int,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate Azure EH component from yaml.

    Adds an empty filter to hass data.
    Tries to get a filter from yaml, if present set to hass data.
    If config is empty after getting the filter, return, otherwise emit
    deprecated warning and pass the rest to the config flow.
    """
    hass.data.setdefault(DOMAIN, {DATA_FILTER: FILTER_SCHEMA({})})
    if DOMAIN not in yaml_config:
        return True
    hass.data[DOMAIN][DATA_FILTER] = yaml_config[DOMAIN].pop(CONF_FILTER)

    if not yaml_config[DOMAIN]:
        return True
    _LOGGER.warning(
        "Loading Azure Event Hub completely via yaml config is deprecated; Only the \
        Filter can be set in yaml, the rest is done through a config flow and has \
        been imported, all other keys but filter can be deleted from configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config[DOMAIN]
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Do the setup based on the config entry and the filter from yaml."""
    hass.data.setdefault(DOMAIN, {DATA_FILTER: FILTER_SCHEMA({})})
    hub = AzureEventHub(
        hass,
        AzureEventHubClient.from_input(**entry.data),
        hass.data[DOMAIN][DATA_FILTER],
        entry.options[CONF_SEND_INTERVAL],
        entry.options.get(CONF_MAX_DELAY),
    )
    try:
        await hub.async_test_connection()
    except EventHubError as err:
        raise ConfigEntryNotReady("Could not connect to Azure Event Hub") from err
    hass.data[DOMAIN][DATA_HUB] = hub
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hub.async_start()
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    hass.data[DOMAIN][DATA_HUB].update_options(entry.options)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN].pop(DATA_HUB)
    await hub.async_stop()
    return True


class AzureEventHub:
    """A event handler class for Azure Event Hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AzureEventHubClient,
        entities_filter: vol.Schema,
        send_interval: int,
        max_delay: int | None = None,
    ) -> None:
        """Initialize the listener."""
        self.hass = hass
        self.queue: asyncio.PriorityQueue[  # pylint: disable=unsubscriptable-object
            tuple[int, tuple[float, Event | None]]
        ] = asyncio.PriorityQueue()
        self._client = client
        self._entities_filter = entities_filter
        self._send_interval = send_interval
        self._max_delay = max_delay if max_delay else DEFAULT_MAX_DELAY
        self._listener_remover: Callable[[], None] | None = None
        self._next_send_remover: Callable[[], None] | None = None
        self.shutdown = False

    async def async_start(self) -> None:
        """Start the hub.

        This suppresses logging and register the listener and
        schedules the first send.
        """
        # suppress the INFO and below logging on the underlying packages,
        # they are very verbose, even at INFO
        logging.getLogger("uamqp").setLevel(logging.WARNING)
        logging.getLogger("azure.eventhub").setLevel(logging.WARNING)

        self._listener_remover = self.hass.bus.async_listen(
            MATCH_ALL, self.async_listen
        )
        # schedule the first send after 10 seconds to capture startup events,
        # after that each send will schedule the next after the interval.
        self._next_send_remover = async_call_later(
            self.hass, self._send_interval, self.async_send
        )

    async def async_stop(self) -> None:
        """Shut down the AEH by queueing None and calling send."""
        if self._next_send_remover:
            self._next_send_remover()
        if self._listener_remover:
            self._listener_remover()
        await self.queue.put((3, (time.monotonic(), None)))
        await self.async_send(None)

    async def async_test_connection(self) -> None:
        """Test the connection to the event hub."""
        await self._client.test_connection()

    async def async_listen(self, event: Event) -> None:
        """Listen for new messages on the bus and queue them for AEH."""
        await self.queue.put((2, (time.monotonic(), event)))

    async def async_send(self, _) -> None:
        """Write preprocessed events to eventhub, with retry."""
        async with self._client.client as client:
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
                self.hass, self._send_interval, self.async_send
            )

    async def fill_batch(self, client) -> tuple[EventDataBatch, int]:
        """Return a batch of events formatted for writing.

        Uses get_nowait instead of await get, because the functions batches and
        doesn't wait for each single event, the send function is called.

        Throws ValueError on add to batch when the EventDataBatch object reaches
        max_size. Put the item back in the queue and the next batch will include
        it.
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
            if time.monotonic() - timestamp <= self._max_delay + self._send_interval:
                try:
                    event_batch.add(event_data)
                except ValueError:
                    dequeue_count -= 1
                    self.queue.task_done()
                    self.queue.put_nowait((1, (timestamp, event)))
                    break
            else:
                dropped += 1

        if dropped:
            _LOGGER.warning(
                "Dropped %d old events, consider filtering messages", dropped
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

    def update_options(self, new_options: dict[str, Any]) -> None:
        """Update options."""
        self._send_interval = new_options[CONF_SEND_INTERVAL]
