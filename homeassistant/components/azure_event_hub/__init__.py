"""Support for Azure Event Hubs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime
import json
import logging
from typing import Any

from azure.eventhub import EventData, EventDataBatch
from azure.eventhub.aio import EventHubProducerClient
from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA, EntityFilter
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import utcnow
from homeassistant.util.hass_dict import HassKey

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
    DEFAULT_MAX_DELAY,
    DOMAIN,
    FILTER_STATES,
)

type AzureEventHubConfigEntry = ConfigEntry[AzureEventHub]

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
DATA_COMPONENT: HassKey[EntityFilter] = HassKey(DOMAIN)


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Activate Azure EH component from yaml.

    Adds an empty filter to hass data.
    Tries to get a filter from yaml, if present set to hass data.
    If config is empty after getting the filter, return, otherwise emit
    deprecated warning and pass the rest to the config flow.
    """
    if DOMAIN not in yaml_config:
        hass.data[DATA_COMPONENT] = FILTER_SCHEMA({})
        return True
    hass.data[DATA_COMPONENT] = yaml_config[DOMAIN].pop(CONF_FILTER)

    if not yaml_config[DOMAIN]:
        return True
    _LOGGER.warning(
        "Loading Azure Event Hub completely via yaml config is deprecated; Only the"
        " Filter can be set in yaml, the rest is done through a config flow and has"
        " been imported, all other keys but filter can be deleted from"
        " configuration.yaml"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=yaml_config[DOMAIN]
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: AzureEventHubConfigEntry
) -> bool:
    """Do the setup based on the config entry and the filter from yaml."""
    hub = AzureEventHub(
        hass,
        entry,
        hass.data[DATA_COMPONENT],
    )
    try:
        await hub.async_test_connection()
    except EventHubError as err:
        raise ConfigEntryNotReady("Could not connect to Azure Event Hub") from err
    entry.runtime_data = hub
    entry.async_on_unload(hub.async_stop)
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hub.async_start()
    return True


async def async_update_listener(
    hass: HomeAssistant, entry: AzureEventHubConfigEntry
) -> None:
    """Update listener for options."""
    entry.runtime_data.update_options(entry.options)


async def async_unload_entry(
    hass: HomeAssistant, entry: AzureEventHubConfigEntry
) -> bool:
    """Unload a config entry."""
    return True


class AzureEventHub:
    """A event handler class for Azure Event Hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        entities_filter: EntityFilter,
    ) -> None:
        """Initialize the listener."""
        self.hass = hass
        self._entry = entry
        self._entities_filter = entities_filter

        self._client = AzureEventHubClient.from_input(**self._entry.data)
        self._send_interval = self._entry.options[CONF_SEND_INTERVAL]
        self._max_delay = self._entry.options.get(CONF_MAX_DELAY, DEFAULT_MAX_DELAY)

        self._shutdown = False
        self._queue: asyncio.PriorityQueue[
            tuple[int, tuple[datetime, State | None]]
        ] = asyncio.PriorityQueue()
        self._listener_remover: Callable[[], None] | None = None
        self._next_send_remover: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Start the hub.

        This suppresses logging and register the listener and
        schedules the first send.

        Suppress the INFO and below logging on the underlying packages,
        they are very verbose, even at INFO.
        """
        logging.getLogger("azure.eventhub").setLevel(logging.WARNING)
        self._listener_remover = self.hass.bus.async_listen(
            MATCH_ALL, self.async_listen
        )
        self._schedule_next_send()

    async def async_stop(self) -> None:
        """Shut down the AEH by queueing None, calling send, join queue."""
        if self._next_send_remover:
            self._next_send_remover()
        if self._listener_remover:
            self._listener_remover()
        await self._queue.put((3, (utcnow(), None)))
        await self.async_send(None)
        await self._queue.join()

    def update_options(self, new_options: Mapping[str, Any]) -> None:
        """Update options."""
        self._send_interval = new_options[CONF_SEND_INTERVAL]

    async def async_test_connection(self) -> None:
        """Test the connection to the event hub."""
        await self._client.test_connection()

    def _schedule_next_send(self) -> None:
        """Schedule the next send."""
        if not self._shutdown:
            self._next_send_remover = async_call_later(
                self.hass, self._send_interval, self.async_send
            )

    async def async_listen(self, event: Event) -> None:
        """Listen for new messages on the bus and queue them for AEH."""
        if state := event.data.get("new_state"):
            await self._queue.put((2, (event.time_fired, state)))

    async def async_send(self, _) -> None:
        """Write preprocessed events to eventhub, with retry."""
        async with self._client.client as client:
            while not self._queue.empty():
                if event_batch := await self.fill_batch(client):
                    _LOGGER.debug("Sending %d event(s)", len(event_batch))
                    try:
                        await client.send_batch(event_batch)
                    except EventHubError as exc:
                        _LOGGER.error("Error in sending events to Event Hub: %s", exc)
        self._schedule_next_send()

    async def fill_batch(self, client: EventHubProducerClient) -> EventDataBatch:
        """Return a batch of events formatted for sending to Event Hub.

        Uses get_nowait instead of await get, because the functions batches and
        doesn't wait for each single event.

        Throws ValueError on add to batch when the EventDataBatch object reaches
        max_size. Put the item back in the queue and the next batch will include
        it.
        """
        event_batch = await client.create_batch()
        dropped = 0
        while not self._shutdown:
            try:
                _, event = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            event_data, dropped = self._parse_event(*event, dropped)
            if not event_data:
                continue
            try:
                event_batch.add(event_data)
            except ValueError:
                self._queue.put_nowait((1, event))
                break

        if dropped:
            _LOGGER.warning(
                "Dropped %d old events, consider filtering messages", dropped
            )
        return event_batch

    def _parse_event(
        self, time_fired: datetime, state: State | None, dropped: int
    ) -> tuple[EventData | None, int]:
        """Parse event by checking if it needs to be sent, and format it."""
        self._queue.task_done()
        if not state:
            self._shutdown = True
            return None, dropped
        if state.state in FILTER_STATES or not self._entities_filter(state.entity_id):
            return None, dropped
        if (utcnow() - time_fired).seconds > self._max_delay + self._send_interval:
            return None, dropped + 1
        return (
            EventData(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8")),
            dropped,
        )
