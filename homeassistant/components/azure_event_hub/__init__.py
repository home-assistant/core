"""Support for Azure Event Hubs."""
import json
import logging
import queue
import threading
import time
from typing import Any, Dict
import asyncio
import voluptuous as vol

from azure.eventhub import (
    EventData,
    EventDataBatch,
    EventHubProducerClient,
    EventHubSharedKeyCredential,
    EventHubError,
)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    MATCH_ALL,
)

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.helpers.json import JSONEncoder

from .const import (
    DOMAIN,
    CONF_EVENT_HUB_CON_STRING,
    CONF_EVENT_HUB_INSTANCE_NAME,
    CONF_EVENT_HUB_NAMESPACE,
    CONF_EVENT_HUB_SAS_KEY,
    CONF_EVENT_HUB_SAS_POLICY,
    CONF_FILTER,
)

_LOGGER = logging.getLogger(__name__)

QUEUE_BACKLOG_SECONDS = 30
PAUSE_WHEN_EMPTY = 5
BATCH_TIMEOUT = 1

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


async def async_setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Azure EH component."""
    _LOGGER.info("Setting up through setup")
    if DOMAIN not in yaml_config:
        return True
    return await _setup(hass, yaml_config[DOMAIN])


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Azure Event Hub from a config entry."""
    _LOGGER.info("Setting up through config flow")
    return await _setup(hass, entry.data)


async def _setup(hass: HomeAssistant, config: Dict[str, Any]):
    """Set up Azure Event Hub from a config entry."""
    entities_filter = config.get(CONF_FILTER, {})
    if CONF_EVENT_HUB_CON_STRING in config:
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
        event_data = EventData(json.dumps(obj=state, cls=JSONEncoder).encode("utf-8"))
        return event_data

    instance = hass.data[DOMAIN] = AEHThread(
        hass, client_args, event_to_event_data, conn_str_client
    )
    _LOGGER.debug("    Instance created.")
    instance.async_initialize()
    instance.start()
    _LOGGER.info("    Instance started.")

    async def shutdown(event: Event):
        """Shut down the thread and client."""
        _LOGGER.info("    Shutting down.")
        instance.queue.put(None)
        instance.join()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.info("    Shutting down.")
    instance = hass.data[DOMAIN]
    instance.queue.put(None)
    instance.join()

    return True


class AEHThread(threading.Thread):
    """A threaded event handler class."""

    def __init__(self, hass, client_args, event_to_event_data, conn_str_client):
        """Initialize the listener."""
        _LOGGER.debug("    Creating Thread.")
        threading.Thread.__init__(self, name="AzureEventHub")
        _LOGGER.info("    Thread Created.")
        self.hass = hass
        self.queue = queue.Queue()
        self._client_args = client_args
        self._conn_str_client = conn_str_client
        self.event_to_event_data = event_to_event_data
        self.write_errors = 0
        self.shutdown = False
        _LOGGER.info("    Initialized AEH.")

    @callback
    def async_initialize(self):
        """Initialize the recorder."""
        self.hass.bus.async_listen(MATCH_ALL, self._event_listener)

    @callback
    def _event_listener(self, event):
        """Listen for new messages on the bus and queue them for AEH."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    @staticmethod
    def batch_timeout():
        """Return number of seconds to wait for more events."""
        return BATCH_TIMEOUT

    def create_batch(self, event_data_batch):
        """Return a batch of events formatted for writing."""
        count = 0
        dropped = 0
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
                    age = time.monotonic() - timestamp
                    try:
                        if age < QUEUE_BACKLOG_SECONDS:
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
        if self._conn_str_client:
            client = EventHubProducerClient.from_connection_string(**self._client_args)
        else:
            client = EventHubProducerClient(**self._client_args)
        event_data_batch = client.create_batch(max_size=10000)

        count, batch_data = self.create_batch(event_data_batch)
        if count > 0:
            _LOGGER.debug("    Sending messages count: %s", str(count))
            with client:
                client.send(batch_data)
                client.close()
        return count

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
