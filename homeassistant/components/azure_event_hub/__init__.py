"""Support for Azure Event Hubs."""
import json
import logging
from typing import Any, Dict

from azure.eventhub import EventData, EventHubClientAsync
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

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EVENT_HUB_CON_STRING): cv.string,
                vol.Optional(CONF_EVENT_HUB_NAMESPACE): cv.string,
                vol.Optional(CONF_EVENT_HUB_INSTANCE_NAME): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_POLICY): cv.string,
                vol.Optional(CONF_EVENT_HUB_SAS_KEY): cv.string,
                vol.Optional(CONF_FILTER, default={}): FILTER_SCHEMA,
            },
            cv.has_at_least_one_key(
                CONF_EVENT_HUB_CON_STRING, CONF_EVENT_HUB_NAMESPACE
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, yaml_config):
    """Activate Azure EH component."""
    config = yaml_config[DOMAIN]
    _LOGGER.debug("Config: %s", config)
    entities_filter = config.get(CONF_FILTER)
    if config.get(CONF_EVENT_HUB_CON_STRING, None):
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

    instance = hass.data[DOMAIN] = AEHThread(
        hass, client_args, conn_str_client, entities_filter
    )
    instance.async_initialize()

    async def async_unload_entry(hass: HomeAssistant):
        """Shut down the AEH Thread."""
        instance.queue.put(None)
        instance.join()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_unload_entry)

    instance.start()
    return await instance.async_ready

    encoder = JSONEncoder()


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
        # suppress the INFO and below logging on the underlying packages, they are very verbose, even at INFO
        logging.getLogger("uamqp").setLevel(logging.WARNING)
        logging.getLogger("azure.eventhub.client_abstract").setLevel(logging.WARNING)

    def event_to_filtered_event_data(self, event: Event):
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
                            if event_data: event_data_batch.add(event_data)
                        else:
                            dropped += 1
                    except ValueError:
                        can_add = False  # EventDataBatch object reaches max_size.
        except queue.Empty:
            pass
        if dropped: _LOGGER.warning("Catching up, dropped %d old events.", dropped)
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
        _LOGGER.debug(
            "Sent event count %d, out of %d events in the queue.",
            len(data_batch),
            dequeue_count,
        )
        await async_sender.send(event_data)

    async def async_shutdown(event: Event):
        """Shut down the client."""
        await client.stop_async()

        try:
            if len(data_batch) > 0:
                with client:
                    client.send_batch(data_batch)
        except EventHubError as exc:
            _LOGGER.error("Error in sending events to Event Hub: %s", exc)
        finally:
            client.close()
            for _ in range(dequeue_count):
                self.queue.task_done()

    def run(self):
        """Process incoming events."""
        self.async_ready.set_result(True)
        while not self.shutdown:
            self.send()
