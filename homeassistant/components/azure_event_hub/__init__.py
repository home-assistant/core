"""Support for Azure Event Hubs."""
import json
import logging
import time
from typing import Any, Dict

from azure.eventhub import EventData
from azure.eventhub.aio import EventHubProducerClient, EventHubSharedKeyCredential
from azure.eventhub.exceptions import EventHubError
import voluptuous as vol

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.json import JSONEncoder

from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_FILTER,
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EVENT_HUB_CON_STRING): cv.string,
                vol.Optional(CONF_EVENT_HUB_NAMESPACE): cv.string,
                vol.Optional(CONF_EVENT_HUB_INSTANCE_NAME): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_POLICY): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_KEY): cv.string,
                vol.Optional(CONF_SEND_INTERVAL, default=5): cv.positive_int,
                vol.Optional(CONF_MAX_DELAY, default=30): cv.positive_int,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            },
            cv.has_at_least_one_key(
                CONF_EVENT_HUB_CON_STRING, CONF_EVENT_HUB_NAMESPACE
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)

ADDITIONAL_ARGS = {"logging_enable": False}


async def async_setup(hass, yaml_config):
    """Activate Azure EH component."""
    config = yaml_config[DOMAIN]
    if config.get(CONF_EVENT_HUB_CON_STRING):
        client_args = {"conn_str": config[CONF_EVENT_HUB_CON_STRING]}
        conn_str_client = True
    else:
        client_args = {
            "fully_qualified_namespace": f"{config[CONF_EVENT_HUB_NAMESPACE]}.servicebus.windows.net",
            "credential": EventHubSharedKeyCredential(
                policy=config[CONF_EVENT_HUB_SAS_POLICY],
                key=config[CONF_EVENT_HUB_SAS_KEY],
            ),
            "eventhub_name": config[CONF_EVENT_HUB_INSTANCE_NAME],
        }
        conn_str_client = False

    instance = hass.data[DOMAIN] = AzureEventHub(
        hass,
        client_args,
        conn_str_client,
        config[CONF_FILTER],
        config[CONF_SEND_INTERVAL],
        config[CONF_MAX_DELAY],
    )

    instance.initialize()
    return await instance.async_ready

    encoder = JSONEncoder()


class AzureEventHub:
    """A event handler class for Azure Event Hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_args: Dict[str, Any],
        conn_str_client: bool,
        entities_filter: vol.Schema,
        send_interval: int,
        max_delay: int,
    ):
        """Initialize the listener."""
        self.hass = hass
        self.queue = asyncio.Queue()
        self._client_args = client_args
        self._conn_str_client = conn_str_client
        self._entities_filter = entities_filter
        self._send_interval = send_interval
        self._max_delay = max_delay + send_interval
        self.async_ready = asyncio.Future()
        self._remove_listener = None
        self.shutdown = False

    def initialize(self):
        """Initialize the recorder, suppress logging and register the callbacks and do the first send."""
        # suppress the INFO and below logging on the underlying packages, they are very verbose, even at INFO
        logging.getLogger("uamqp").setLevel(logging.WARNING)
        logging.getLogger("azure.eventhub").setLevel(logging.WARNING)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)
        self._remove_listener = self.hass.bus.async_listen(MATCH_ALL, self.async_listen)
        self.hass.async_run_job(self.async_send, None)
        self.async_ready.set_result(True)

    @callback
    def async_shutdown(self, _: Event):
        """Shut down the AEH by queueing None and calling send."""
        self._remove_listener()
        self.hass.async_create_task(self.queue.put((time.monotonic(), None)))
        self.hass.async_create_task(self.async_send(None))

    @callback
    def async_listen(self, event: Event):
        """Listen for new messages on the bus and queue them for AEH."""
        self.hass.async_create_task(self.queue.put((time.monotonic(), event)))

    async def async_send(self, _):
        """Write preprocessed events to eventhub, with retry."""
        client = self._get_client()
        async with client:
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
        await client.close()

        if not self.shutdown:
            async_call_later(self.hass, self._send_interval, self.async_send)

    async def fill_batch(self, client):
        """Return a batch of events formatted for writing."""
        event_batch = await client.create_batch()
        dequeue_count = 0
        dropped = 0
        while not self.shutdown:
            try:
                # nowait is used because send func is run regularly
                timestamp, event = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            dequeue_count += 1

            if not event:
                self.shutdown = True
                break

            event_data = self._event_to_filtered_event_data(event)
            if event_data:
                if time.monotonic() - timestamp <= self._max_delay:
                    try:
                        event_batch.add(event_data)
                    except ValueError:
                        break  # EventDataBatch object reaches max_size.
                else:
                    dropped += 1

        if dropped:
            _LOGGER.warning(
                "Dropped %d old events, consider increasing the max_delay", dropped
            )

        return event_batch, dequeue_count

    def _event_to_filtered_event_data(self, event: Event):
        """Send states to Event Hub."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not self._entities_filter(state.entity_id)
        ):
            return None
        return EventData(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8"))

    def _get_client(self):
        """Get a Event Producer Client."""
        if self._conn_str_client:
            return EventHubProducerClient.from_connection_string(
                **self._client_args, **ADDITIONAL_ARGS
            )
        else:
            return EventHubProducerClient(**self._client_args, **ADDITIONAL_ARGS)
