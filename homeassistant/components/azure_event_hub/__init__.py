"""Support for Azure Event Hubs."""
import asyncio
import json
import logging
import queue
import threading
import time
from typing import Any, Dict

from azure.eventhub import (
    EventData,
    EventDataBatch,
    EventHubError,
    EventHubProducerClient,
    EventHubSharedKeyCredential,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.json import JSONEncoder

from .config_flow import AzureEventHubConfigFlow  # noqa: F401
from .const import (
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_FILTER,
    DOMAIN,
    FILTER_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

QUEUE_BACKLOG_SECONDS = 30
PAUSE_WHEN_EMPTY = 5
BATCH_TIMEOUT = 1

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EVENT_HUB_CON_STRING, ""): cv.string,
                vol.Optional(CONF_EVENT_HUB_NAMESPACE, ""): cv.string,
                vol.Optional(CONF_EVENT_HUB_INSTANCE_NAME, ""): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_POLICY, ""): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_KEY, ""): cv.string,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            },
            cv.has_at_least_one_key(
                CONF_EVENT_HUB_CON_STRING, CONF_EVENT_HUB_NAMESPACE
            ),
            extra=vol.ALLOW_EXTRA,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Activate Azure EH component."""
    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Azure Event Hub from a config entry."""
    config = entry.data
    entities_filter = config.get(CONF_FILTER, {})
    if isinstance(entities_filter, dict):
        if entities_filter == {}:
            entities_filter = generate_filter(**FILTER_SCHEMA({}))
        else:
            entities_filter = generate_filter(**entities_filter)
    if config.get(CONF_EVENT_HUB_CON_STRING, None):
        client_args = {"conn_str": config[CONF_EVENT_HUB_CON_STRING]}
        conn_str_client = True
    else:
        client_args = {
            "host": f"{config[CONF_EVENT_HUB_NAMESPACE]}.servicebus.windows.net",
            "credential": EventHubSharedKeyCredential(
                policy=config[CONF_EVENT_HUB_SAS_POLICY],
                key=config[CONF_EVENT_HUB_SAS_KEY],
            ),
            "event_hub_path": config[CONF_EVENT_HUB_INSTANCE_NAME],
        }
        conn_str_client = False

    instance = hass.data[DOMAIN] = AEHThread(
        hass, client_args, conn_str_client, entities_filter
    )
    instance.async_initialize()
    instance.start()

    return await instance.async_ready


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info("    Shutting down.")
    instance = hass.data[DOMAIN]
    instance.queue.put(None)
    instance.join()
    return True


class AEHThread(threading.Thread):
    """A threaded event handler class."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_args: Dict[str, Any],
        conn_str_client: bool,
        entities_filter: vol.Schema,
    ):
        """Initialize the listener."""
        threading.Thread.__init__(self, name="AzureEventHub")
        self.hass = hass
        self.queue = queue.Queue()
        self._client_args = client_args
        self._conn_str_client = conn_str_client
        self._entities_filter = entities_filter
        self.async_ready = asyncio.Future()
        self.write_errors = 0
        self.shutdown = False
        # surpress the INFO and below logging on the underlying packages, they are very verbose, even at INFO
        logging.getLogger("uamqp").setLevel(logging.WARNING)
        logging.getLogger("azure.eventhub.client_abstract").setLevel(logging.WARNING)

        _LOGGER.info("    Initialized AEH Thread.")

    def event_to_filtered_event_data(self, event: Event):
        """Send states to Event Hub."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not self._entities_filter(state.entity_id)
        ):
            return
        event_data = EventData(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8"))
        return event_data

    @callback
    def _event_listener(self, event: Event):
        """Listen for new messages on the bus and queue them for AEH."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    @callback
    def async_initialize(self):
        """Initialize the recorder."""
        self.hass.bus.async_listen(MATCH_ALL, self._event_listener)

    @staticmethod
    def batch_timeout():
        """Return number of seconds to wait for more events."""
        return BATCH_TIMEOUT

    def fill_batch(self, event_data_batch: EventDataBatch):
        """Return a batch of events formatted for writing."""
        dequeue_count = 0
        dropped = 0
        can_add = True
        try:  # pylint: disable=too-many-nested-blocks
            while can_add and not self.shutdown:
                timeout = None if dequeue_count == 0 else self.batch_timeout()
                item = self.queue.get(timeout=timeout)
                dequeue_count += 1
                if item is None:
                    self.shutdown = True
                else:
                    timestamp, event = item
                    age = time.monotonic() - timestamp
                    try:
                        if age < QUEUE_BACKLOG_SECONDS:
                            event_data = self.event_to_filtered_event_data(event)
                            if event_data:
                                _LOGGER.debug(
                                    "      Event data json: %s", str(event_data)
                                )
                                event_data_batch.try_add(event_data)
                        else:
                            dropped += 1
                    except ValueError:
                        can_add = False  # EventDataBatch object reaches max_size.
        except queue.Empty:
            pass

        if dropped:
            _LOGGER.warning("    Catching up, dropped %d old events", dropped)
        return event_data_batch, dequeue_count

    def send(self):
        """Write preprocessed events to eventhub, with retry."""
        additional_args = {"logging_enable": False}
        if self._conn_str_client:
            client = EventHubProducerClient.from_connection_string(
                **self._client_args, **additional_args
            )
        else:
            client = EventHubProducerClient(**self._client_args, **additional_args)
        data_batch, dequeue_count = self.fill_batch(client.create_batch(max_size=10000))
        _LOGGER.info(
            "Sent event count %s, out of %s events in the queue.",
            str(len(data_batch)),
            str(dequeue_count),
        )

        try:
            if len(data_batch) > 0:
                with client:
                    client.send(data_batch)
        except EventHubError as exc:
            _LOGGER.error("Error in sending events to Event Hub: %s", exc)
        finally:
            client.close()
            for _ in range(dequeue_count):
                self.queue.task_done()

    def run(self):
        """Process incoming events."""

        @callback
        def register():
            """Post connection initialize."""
            self.async_ready.set_result(True)
            _LOGGER.debug("Ready to go!")

            def shutdown(event):
                """Shut down the AEH Thread."""
                self.queue.put(None)
                self.join()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        self.hass.add_job(register)
        _LOGGER.debug("    Azure Event Hub Thread Running")
        while not self.shutdown:
            self.send()
        _LOGGER.debug("Goodbye, thank you for using Azure Event Hub!")
