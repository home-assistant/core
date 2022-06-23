"""Support for Zabbix."""
from contextlib import suppress
import json
import logging
import math
import queue
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urljoin

from pyzabbix import ZabbixAPI, ZabbixAPIException, ZabbixMetric, ZabbixSender
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import event as event_helper, state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
)
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_PUBLISH_STATES_HOST = "publish_states_host"

DEFAULT_SSL = False
DEFAULT_PATH = "zabbix"
DOMAIN = "zabbix"

TIMEOUT = 5
RETRY_DELAY = 20
QUEUE_BACKLOG_SECONDS = 30
RETRY_INTERVAL = 60  # seconds
RETRY_MESSAGE = f"%s Retrying in {RETRY_INTERVAL} seconds."

BATCH_TIMEOUT = 1
BATCH_BUFFER_SIZE = 100

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PUBLISH_STATES_HOST): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Zabbix component."""

    conf = config[DOMAIN]
    protocol = "https" if conf[CONF_SSL] else "http"

    url = urljoin(f"{protocol}://{conf[CONF_HOST]}", conf[CONF_PATH])
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    publish_states_host = conf.get(CONF_PUBLISH_STATES_HOST)

    entities_filter = convert_include_exclude_filter(conf)

    try:
        zapi = ZabbixAPI(url=url, user=username, password=password)
        _LOGGER.info("Connected to Zabbix API Version %s", zapi.api_version())
    except ZabbixAPIException as login_exception:
        _LOGGER.error("Unable to login to the Zabbix API: %s", login_exception)
        return False
    except HTTPError as http_error:
        _LOGGER.error("HTTPError when connecting to Zabbix API: %s", http_error)
        zapi = None
        _LOGGER.error(RETRY_MESSAGE, http_error)
        event_helper.call_later(
            hass,
            RETRY_INTERVAL,
            lambda _: setup(hass, config),  # type: ignore[arg-type,return-value]
        )
        return True

    hass.data[DOMAIN] = zapi

    def event_to_metrics(event, float_keys, string_keys):
        """Add an event to the outgoing Zabbix list."""
        state = event.data.get("new_state")
        if state is None or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE):
            return

        entity_id = state.entity_id
        if not entities_filter(entity_id):
            return

        floats = {}
        strings = {}
        try:
            _state_as_value = float(state.state)
            floats[entity_id] = _state_as_value
        except ValueError:
            try:
                _state_as_value = float(state_helper.state_as_number(state))
                floats[entity_id] = _state_as_value
            except ValueError:
                strings[entity_id] = state.state

        for key, value in state.attributes.items():
            # For each value we try to cast it as float
            # But if we can not do it we store the value
            # as string
            attribute_id = f"{entity_id}/{key}"
            try:
                float_value = float(value)
            except (ValueError, TypeError):
                float_value = None
            if float_value is None or not math.isfinite(float_value):
                strings[attribute_id] = str(value)
            else:
                floats[attribute_id] = float_value

        metrics = []
        float_keys_count = len(float_keys)
        float_keys.update(floats)
        if len(float_keys) != float_keys_count:
            floats_discovery = []
            for float_key in float_keys:
                floats_discovery.append({"{#KEY}": float_key})
            metric = ZabbixMetric(
                publish_states_host,
                "homeassistant.floats_discovery",
                json.dumps(floats_discovery),
            )
            metrics.append(metric)
        for key, value in floats.items():
            metric = ZabbixMetric(
                publish_states_host, f"homeassistant.float[{key}]", value
            )
            metrics.append(metric)

        string_keys.update(strings)
        return metrics

    if publish_states_host:
        zabbix_sender = ZabbixSender(zabbix_server=conf[CONF_HOST])
        instance = ZabbixThread(hass, zabbix_sender, event_to_metrics)
        instance.setup(hass)

    return True


class ZabbixThread(threading.Thread):
    """A threaded event handler class."""

    MAX_TRIES = 3

    def __init__(self, hass, zabbix_sender, event_to_metrics):
        """Initialize the listener."""
        threading.Thread.__init__(self, name="Zabbix")
        self.queue = queue.Queue()
        self.zabbix_sender = zabbix_sender
        self.event_to_metrics = event_to_metrics
        self.write_errors = 0
        self.shutdown = False
        self.float_keys = set()
        self.string_keys = set()

    def setup(self, hass):
        """Set up the thread and start it."""
        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self._shutdown)
        self.start()
        _LOGGER.debug("Started publishing state changes to Zabbix")

    def _shutdown(self, event):
        """Shut down the thread."""
        self.queue.put(None)
        self.join()

    @callback
    def _event_listener(self, event):
        """Listen for new messages on the bus and queue them for Zabbix."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    def get_metrics(self):
        """Return a batch of events formatted for writing."""
        queue_seconds = QUEUE_BACKLOG_SECONDS + self.MAX_TRIES * RETRY_DELAY

        count = 0
        metrics = []

        dropped = 0

        with suppress(queue.Empty):
            while len(metrics) < BATCH_BUFFER_SIZE and not self.shutdown:
                timeout = None if count == 0 else BATCH_TIMEOUT
                item = self.queue.get(timeout=timeout)
                count += 1

                if item is None:
                    self.shutdown = True
                else:
                    timestamp, event = item
                    age = time.monotonic() - timestamp

                    if age < queue_seconds:
                        event_metrics = self.event_to_metrics(
                            event, self.float_keys, self.string_keys
                        )
                        if event_metrics:
                            metrics += event_metrics
                    else:
                        dropped += 1

        if dropped:
            _LOGGER.warning("Catching up, dropped %d old events", dropped)

        return count, metrics

    def write_to_zabbix(self, metrics):
        """Write preprocessed events to zabbix, with retry."""

        for retry in range(self.MAX_TRIES + 1):
            try:
                self.zabbix_sender.send(metrics)

                if self.write_errors:
                    _LOGGER.error("Resumed, lost %d events", self.write_errors)
                    self.write_errors = 0

                _LOGGER.debug("Wrote %d metrics", len(metrics))
                break
            except OSError as err:
                if retry < self.MAX_TRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    if not self.write_errors:
                        _LOGGER.error("Write error: %s", err)
                    self.write_errors += len(metrics)

    def run(self):
        """Process incoming events."""
        while not self.shutdown:
            count, metrics = self.get_metrics()
            if metrics:
                self.write_to_zabbix(metrics)
            for _ in range(count):
                self.queue.task_done()
