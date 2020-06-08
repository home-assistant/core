"""Support for Zabbix."""
import logging
from urllib.parse import urljoin

from pyzabbix import ZabbixAPI, ZabbixAPIException, ZabbixMetric, ZabbixSender
import json
import math
from pprint import pprint
import queue
import threading
import time
import voluptuous as vol

from homeassistant.const import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import event as event_helper, state as state_helper
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_RETRY_COUNT = "max_retries"

DEFAULT_SSL = False
DEFAULT_PATH = "zabbix"
DOMAIN = "zabbix"

TIMEOUT = 5
RETRY_DELAY = 20
QUEUE_BACKLOG_SECONDS = 30
RETRY_INTERVAL = 60  # seconds

BATCH_TIMEOUT = 1
BATCH_BUFFER_SIZE = 100

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_RETRY_COUNT, default=0): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Zabbix component."""

    conf = config[DOMAIN]
    protocol = "https" if conf[CONF_SSL] else "http"

    url = urljoin(f"{protocol}://{conf[CONF_HOST]}", conf[CONF_PATH])
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    # todo: give good name and make configurable
    hostname = "homeassistant"

    include = conf.get(CONF_INCLUDE, {})
    exclude = conf.get(CONF_EXCLUDE, {})
    whitelist_e = set(include.get(CONF_ENTITIES, []))
    whitelist_d = set(include.get(CONF_DOMAINS, []))
    blacklist_e = set(exclude.get(CONF_ENTITIES, []))
    blacklist_d = set(exclude.get(CONF_DOMAINS, []))

    max_tries = conf.get(CONF_RETRY_COUNT)

    try:
        zapi = ZabbixAPI(url=url, user=username, password=password)
        _LOGGER.info("Connected to Zabbix API Version %s", zapi.api_version())
    except ZabbixAPIException as login_exception:
        _LOGGER.error("Unable to login to the Zabbix API: %s", login_exception)
        return False

    zabbix_sender = ZabbixSender(zabbix_server=conf[CONF_HOST])
    _LOGGER.info("Initialized Zabbix sender")

    def event_to_metrics(event, float_keys, string_keys):
        """Add an event to the outgoing Zabbix list."""
        state = event.data.get("new_state")
        entity_id = state.entity_id
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or entity_id in blacklist_e
            or state.domain in blacklist_d
        ):
            return

        floats = {}
        strings = {}
        try:
            if (
                (whitelist_e or whitelist_d)
                and entity_id not in whitelist_e
                and state.domain not in whitelist_d
            ):
                return

            _state_as_value = float(state.state)
            floats[entity_id] = _state_as_value
        except ValueError:
            try:
                _state_as_value = float(state_helper.state_as_number(state))
                floats[entity_id] = _state_as_value
            except ValueError:
                strings[entity_id] = state.state

        # "time": event.time_fired,

        for key, value in state.attributes.items():
            # For each value we try to cast it as float
            # But if we can not do it we store the value
            # as string
            attribute_id = f"{entity_id}/{key}"
            try:
                float_value = float(value)
                if math.isfinite(float_value):
                    floats[attribute_id] = float_value
                else:
                    strings[attribute_id] = str(value)
            except (ValueError, TypeError):
                strings[attribute_id] = str(value)

        metrics = []
        float_keys_count = len(float_keys)
        float_keys.update(floats.keys())
        if len(float_keys) != float_keys_count:
            floats_discovery = []
            for float_key in float_keys:
                floats_discovery.append({"{#KEY}": float_key})
            m = ZabbixMetric(hostname, 'homeassistant.floats_discovery', json.dumps(floats_discovery))
            #pprint(json.dumps(floats_discovery))
            metrics.append(m)
        for key, value in floats.items():
            m = ZabbixMetric(hostname, f"homeassistant.float[{key}]", value)
            metrics.append(m)

        string_keys |= strings.keys()
        return metrics


    hass.data[DOMAIN] = zapi
    instance = ZabbixThread(hass, zabbix_sender, event_to_metrics, max_tries)
    instance.start()
    _LOGGER.info("Started ZabbixThread")

    def shutdown(event):
        """Shut down the thread."""
        instance.queue.put(None)
        instance.join()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class ZabbixThread(threading.Thread):
    """A threaded event handler class."""

    def __init__(self, hass, zabbix_sender, event_to_metrics, max_tries):
        """Initialize the listener."""
        _LOGGER.info("ZabbixThread 1")
        threading.Thread.__init__(self, name="Zabbix")
        self.queue = queue.Queue()
        self.zabbix_sender = zabbix_sender
        self.event_to_metrics = event_to_metrics
        self.max_tries = max_tries
        self.write_errors = 0
        self.shutdown = False
        self.float_keys = set([])
        self.string_keys = set([])

        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)
        _LOGGER.info("ZabbixThread 2")

    def _event_listener(self, event):
        """Listen for new messages on the bus and queue them for Zabbix."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    @staticmethod
    def batch_timeout():
        """Return number of seconds to wait for more events."""
        return BATCH_TIMEOUT

    def get_metrics(self):
        """Return a batch of events formatted for writing."""
        queue_seconds = QUEUE_BACKLOG_SECONDS + self.max_tries * RETRY_DELAY

        count = 0
        metrics = []

        dropped = 0

        try:
            while len(metrics) < BATCH_BUFFER_SIZE and not self.shutdown:
                timeout = None if count == 0 else self.batch_timeout()
                item = self.queue.get(timeout=timeout)
                count += 1

                if item is None:
                    self.shutdown = True
                else:
                    timestamp, event = item
                    age = time.monotonic() - timestamp

                    if age < queue_seconds:
                        event_metrics = self.event_to_metrics(event, self.float_keys, self.string_keys)
                        if event_metrics:
                            metrics += event_metrics
                    else:
                        dropped += 1

        except queue.Empty:
            pass

        if dropped:
            _LOGGER.warning("Catching up, dropped %d old events", dropped)

        return count, metrics

    def write_to_zabbix(self, metrics):
        """Write preprocessed events to zabbix, with retry."""

        for retry in range(self.max_tries + 1):
            try:
                self.zabbix_sender.send(metrics)

                if self.write_errors:
                    _LOGGER.error("Resumed, lost %d events", self.write_errors)
                    self.write_errors = 0

                _LOGGER.debug("Wrote %d metrics", len(metrics))
                break
            except (
                #exceptions.InfluxDBClientError,
                #exceptions.InfluxDBServerError,
                OSError,
            ) as err:
                if retry < self.max_tries:
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

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()
