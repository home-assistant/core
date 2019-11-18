"""Support for Azure Event Hubs."""
import json
import logging
import queue
import threading
import time
from typing import Any, Dict

import voluptuous as vol

from azure.eventhub import (
    EventData,
    EventDataBatch,
    EventHubProducerClient,
    EventHubSharedKeyCredential,
    EventHubSASTokenCredential,
    EventHubError,
)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder

_LOGGER = logging.getLogger(__name__)

DOMAIN = "azure_event_hub"

CONF_EVENT_HUB_NAMESPACE = "event_hub_namespace"
CONF_EVENT_HUB_INSTANCE_NAME = "event_hub_instance_name"
CONF_EVENT_HUB_SAS_POLICY = "event_hub_sas_policy"
CONF_EVENT_HUB_SAS_KEY = "event_hub_sas_key"
CONF_EVENT_HUB_CON_STRING = "event_hub_connection_string"
CONF_IOT_HUB_CON_STRING = "iot_hub_connection_string"
CONF_FILTER = "filter"

TIMEOUT = 5
RETRY_DELAY = 20
QUEUE_BACKLOG_SECONDS = 30
RETRY_INTERVAL = 60  # seconds
KEEP_ALIVE_INTERVAL = 300
PAUSE_WHEN_EMPTY = 5
MAX_TRIES = 3
BATCH_TIMEOUT = 1
BATCH_BUFFER_SIZE = 100

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            vol.Schema(
                {
                    vol.Required(CONF_EVENT_HUB_CON_STRING): cv.string,
                    vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
                }
            ),
            vol.Schema(
                {
                    vol.Required(CONF_EVENT_HUB_NAMESPACE): cv.string,
                    vol.Required(CONF_EVENT_HUB_INSTANCE_NAME): cv.string,
                    vol.Required(CONF_EVENT_HUB_SAS_POLICY): cv.string,
                    vol.Required(CONF_EVENT_HUB_SAS_KEY): cv.string,
                    vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Azure EH component."""
    config = yaml_config[DOMAIN]

    entities_filter = config[CONF_FILTER]
    if CONF_EVENT_HUB_CON_STRING in config:
        client_args = {"conn_str": config[CONF_EVENT_HUB_CON_STRING]}
    else:
        client_args = {
            "host": f"{config[CONF_EVENT_HUB_NAMESPACE]}.servicebus.windows.net",
            "credential": EventHubSharedKeyCredential(
                policy=config[CONF_EVENT_HUB_SAS_POLICY],
                key=config[CONF_EVENT_HUB_SAS_KEY],
            ),
            "event_hub_path": config[CONF_EVENT_HUB_INSTANCE_NAME],
        }

    # encoder = JSONEncoder()
    _LOGGER.debug("    Client created.")

    def event_to_event_data(event: Event):
        """Send states to Event Hub."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not entities_filter(state.entity_id)
        ):
            return
        event_data = EventData(
            json.dumps(obj=state, cls=JSONEncoder).encode("utf-8")
            # json.dumps(obj=state.as_dict(), default=encoder.default).encode("utf-8")
        )
        return event_data

    instance = hass.data[DOMAIN] = AEHThread(hass, client_args, event_to_event_data)
    _LOGGER.debug("    Instance created.")
    instance.start()
    _LOGGER.info("    Instance started.")

    # async_sender = client.add_async_sender()
    # await client.run_async()

    def shutdown(event: Event):
        """Shut down the thread and client."""
        _LOGGER.info("    Shutting down.")
        instance.queue.put(None)
        instance.join()
        # client.close()

    # hass.bus.async_listen(EVENT_STATE_CHANGED, async_send_to_event_hub)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class AEHThread(threading.Thread):
    """A threaded event handler class."""

    def __init__(self, hass, client_args, event_to_event_data):
        """Initialize the listener."""
        _LOGGER.debug("    Creating Thread.")
        threading.Thread.__init__(self, name="AzureEventHub")
        _LOGGER.info("    Thread Created.")
        self.queue = queue.Queue()
        self.client_args = client_args
        # self.client = aeh_client
        self.event_to_event_data = event_to_event_data
        self.write_errors = 0
        self.shutdown = False
        _LOGGER.debug("    Adding event listener to hass bus.")
        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)
        _LOGGER.info("    Initialized AEH.")

    def _event_listener(self, event):
        """Listen for new messages on the bus and queue them for AEH."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    @staticmethod
    def batch_timeout():
        """Return number of seconds to wait for more events."""
        return BATCH_TIMEOUT

    def create_batch(self, client):
        """Return a batch of events formatted for writing."""
        # _LOGGER.info("    Creating batch of events.")
        queue_seconds = QUEUE_BACKLOG_SECONDS  # + self.max_tries * RETRY_DELAY
        # _LOGGER.info("    Queue size:" + str(self.queue.qsize()))
        event_data_batch = client.create_batch(max_size=10000)
        count = 0
        dropped = 0
        # if not self.queue.empty():
        _LOGGER.debug("    Queue size: %s", str(self.queue.qsize()))
        can_add = True
        try:
            while can_add and not self.shutdown:
                timeout = None if count == 0 else self.batch_timeout()
                item = self.queue.get(timeout=timeout)
                if item is None:
                    self.shutdown = True
                else:
                    timestamp, event = item
                    # _LOGGER.debug("      Event data item: " + str(event))
                    age = time.monotonic() - timestamp
                    try:
                        if age < queue_seconds:
                            event_data = self.event_to_event_data(event)
                            _LOGGER.debug("      Event data json: %s", str(event_data))
                            if event_data:
                                event_data_batch.try_add(event_data)
                                count += 1
                        else:
                            dropped += 1
                    except ValueError:
                        can_add = False  # EventDataBatch object reaches max_size.
        except queue.Empty:
            pass

        if dropped:
            _LOGGER.warning("Catching up, dropped %d old events", dropped)
        return count, event_data_batch

    def send(self):
        """Write preprocessed events to eventhub, with retry."""
        if "conn_str" in self.client_args:
            client = EventHubProducerClient.from_connection_string(**self.client_args)
        else:
            client = EventHubProducerClient(**self.client_args)

        count, batch_data = self.create_batch(client)
        if count > 0:
            _LOGGER.debug("    Sending messages count: %s", str(count))
            with client:
                client.send(batch_data)
                client.close()
        return count

    # def get_events_json(self):
    #     """Return a batch of events formatted for writing."""
    #     queue_seconds = QUEUE_BACKLOG_SECONDS + self.max_tries * RETRY_DELAY

    #     count = 0
    #     events = []

    #     dropped = 0

    #     try:
    #         while len(events) < BATCH_BUFFER_SIZE and not self.shutdown:
    #             timeout = None if count == 0 else self.batch_timeout()
    #             item = self.queue.get(timeout=timeout)
    #             count += 1

    #             if item is None:
    #                 self.shutdown = True
    #             else:
    #                 timestamp, event = item
    #                 age = time.monotonic() - timestamp

    #                 if age < queue_seconds:
    #                     event_json = self.event_to_json(event)
    #                     if event_json:
    #                         events.append(event_json)
    #                 else:
    #                     dropped += 1

    #     except queue.Empty:
    #         pass

    #     if dropped:
    #         _LOGGER.warning("Catching up, dropped %d old events", dropped)

    #     return count, events

    # async def write_to_eventhub(self, events):
    #     """Write preprocessed events to eventhub, with retry."""
    #     for retry in range(self.max_tries + 1):
    #         try:
    #             await self.async_sender.async_send_to_event_hub(events)
    #         except AttributeError as err:
    #             if retry < self.max_tries:
    #                 time.sleep(RETRY_DELAY)
    #                 await self.async_sender.reconnect_async()
    #                 await self.async_sender.async_send_to_event_hub(events)
    #             else:
    #                 _LOGGER.error("Send error: %s", err)

    def run(self):
        """Process incoming events."""
        _LOGGER.debug("    Azure Event Hub Thread Running")
        while not self.shutdown:
            # count, events = self.get_events_json()
            # if events:
            count = self.send()
            _LOGGER.debug("    Sent message count: %s", str(count))
            for _ in range(count):
                self.queue.task_done()
            if count == 0:
                time.sleep(PAUSE_WHEN_EMPTY)

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()
