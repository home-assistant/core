"""Support for sending data to an Influx database."""
import logging
import math
import queue
import re
import threading
import time

from influxdb import InfluxDBClient, exceptions
import requests.exceptions
import voluptuous as vol

from homeassistant.const import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import event as event_helper, state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_values import EntityValues

_LOGGER = logging.getLogger(__name__)

CONF_DB_NAME = "database"
CONF_TAGS = "tags"
CONF_DEFAULT_MEASUREMENT = "default_measurement"
CONF_OVERRIDE_MEASUREMENT = "override_measurement"
CONF_TAGS_ATTRIBUTES = "tags_attributes"
CONF_COMPONENT_CONFIG = "component_config"
CONF_COMPONENT_CONFIG_GLOB = "component_config_glob"
CONF_COMPONENT_CONFIG_DOMAIN = "component_config_domain"
CONF_RETRY_COUNT = "max_retries"

DEFAULT_DATABASE = "home_assistant"
DEFAULT_VERIFY_SSL = True
DOMAIN = "influxdb"

TIMEOUT = 5
RETRY_DELAY = 20
QUEUE_BACKLOG_SECONDS = 30
RETRY_INTERVAL = 60  # seconds

BATCH_TIMEOUT = 1
BATCH_BUFFER_SIZE = 100

COMPONENT_CONFIG_SCHEMA_ENTRY = vol.Schema(
    {vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            vol.Schema(
                {
                    vol.Optional(CONF_HOST): cv.string,
                    vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
                    vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
                    vol.Optional(CONF_EXCLUDE, default={}): vol.Schema(
                        {
                            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                            vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                                cv.ensure_list, [cv.string]
                            ),
                        }
                    ),
                    vol.Optional(CONF_INCLUDE, default={}): vol.Schema(
                        {
                            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                            vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                                cv.ensure_list, [cv.string]
                            ),
                        }
                    ),
                    vol.Optional(CONF_DB_NAME, default=DEFAULT_DATABASE): cv.string,
                    vol.Optional(CONF_PORT): cv.port,
                    vol.Optional(CONF_SSL): cv.boolean,
                    vol.Optional(CONF_RETRY_COUNT, default=0): cv.positive_int,
                    vol.Optional(CONF_DEFAULT_MEASUREMENT): cv.string,
                    vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string,
                    vol.Optional(CONF_TAGS, default={}): vol.Schema(
                        {cv.string: cv.string}
                    ),
                    vol.Optional(CONF_TAGS_ATTRIBUTES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                    vol.Optional(
                        CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                    ): cv.boolean,
                    vol.Optional(CONF_COMPONENT_CONFIG, default={}): vol.Schema(
                        {cv.entity_id: COMPONENT_CONFIG_SCHEMA_ENTRY}
                    ),
                    vol.Optional(CONF_COMPONENT_CONFIG_GLOB, default={}): vol.Schema(
                        {cv.string: COMPONENT_CONFIG_SCHEMA_ENTRY}
                    ),
                    vol.Optional(CONF_COMPONENT_CONFIG_DOMAIN, default={}): vol.Schema(
                        {cv.string: COMPONENT_CONFIG_SCHEMA_ENTRY}
                    ),
                }
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RE_DIGIT_TAIL = re.compile(r"^[^\.]*\d+\.?\d+[^\.]*$")
RE_DECIMAL = re.compile(r"[^\d.]+")


def setup(hass, config):
    """Set up the InfluxDB component."""

    conf = config[DOMAIN]

    kwargs = {
        "database": conf[CONF_DB_NAME],
        "verify_ssl": conf[CONF_VERIFY_SSL],
        "timeout": TIMEOUT,
    }

    if CONF_HOST in conf:
        kwargs["host"] = conf[CONF_HOST]

    if CONF_PORT in conf:
        kwargs["port"] = conf[CONF_PORT]

    if CONF_USERNAME in conf:
        kwargs["username"] = conf[CONF_USERNAME]

    if CONF_PASSWORD in conf:
        kwargs["password"] = conf[CONF_PASSWORD]

    if CONF_SSL in conf:
        kwargs["ssl"] = conf[CONF_SSL]

    include = conf.get(CONF_INCLUDE, {})
    exclude = conf.get(CONF_EXCLUDE, {})
    whitelist_e = set(include.get(CONF_ENTITIES, []))
    whitelist_d = set(include.get(CONF_DOMAINS, []))
    blacklist_e = set(exclude.get(CONF_ENTITIES, []))
    blacklist_d = set(exclude.get(CONF_DOMAINS, []))
    tags = conf.get(CONF_TAGS)
    tags_attributes = conf.get(CONF_TAGS_ATTRIBUTES)
    default_measurement = conf.get(CONF_DEFAULT_MEASUREMENT)
    override_measurement = conf.get(CONF_OVERRIDE_MEASUREMENT)
    component_config = EntityValues(
        conf[CONF_COMPONENT_CONFIG],
        conf[CONF_COMPONENT_CONFIG_DOMAIN],
        conf[CONF_COMPONENT_CONFIG_GLOB],
    )
    max_tries = conf.get(CONF_RETRY_COUNT)

    try:
        influx = InfluxDBClient(**kwargs)
        influx.write_points([])
    except (exceptions.InfluxDBClientError, requests.exceptions.ConnectionError) as exc:
        _LOGGER.warning(
            "Database host is not accessible due to '%s', please "
            "check your entries in the configuration file (host, "
            "port, etc.) and verify that the database exists and is "
            "READ/WRITE. Retrying again in %s seconds.",
            exc,
            RETRY_INTERVAL,
        )
        event_helper.call_later(hass, RETRY_INTERVAL, lambda _: setup(hass, config))
        return True

    def event_to_json(event):
        """Add an event to the outgoing Influx list."""
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or state.entity_id in blacklist_e
            or state.domain in blacklist_d
        ):
            return

        try:
            if (
                (whitelist_e or whitelist_d)
                and state.entity_id not in whitelist_e
                and state.domain not in whitelist_d
            ):
                return

            _include_state = _include_value = False

            _state_as_value = float(state.state)
            _include_value = True
        except ValueError:
            try:
                _state_as_value = float(state_helper.state_as_number(state))
                _include_state = _include_value = True
            except ValueError:
                _include_state = True

        include_uom = True
        measurement = component_config.get(state.entity_id).get(
            CONF_OVERRIDE_MEASUREMENT
        )
        if measurement in (None, ""):
            if override_measurement:
                measurement = override_measurement
            else:
                measurement = state.attributes.get("unit_of_measurement")
                if measurement in (None, ""):
                    if default_measurement:
                        measurement = default_measurement
                    else:
                        measurement = state.entity_id
                else:
                    include_uom = False

        json = {
            "measurement": measurement,
            "tags": {"domain": state.domain, "entity_id": state.object_id},
            "time": event.time_fired,
            "fields": {},
        }
        if _include_state:
            json["fields"]["state"] = state.state
        if _include_value:
            json["fields"]["value"] = _state_as_value

        for key, value in state.attributes.items():
            if key in tags_attributes:
                json["tags"][key] = value
            elif key != "unit_of_measurement" or include_uom:
                # If the key is already in fields
                if key in json["fields"]:
                    key = key + "_"
                # Prevent column data errors in influxDB.
                # For each value we try to cast it as float
                # But if we can not do it we store the value
                # as string add "_str" postfix to the field key
                try:
                    json["fields"][key] = float(value)
                except (ValueError, TypeError):
                    new_key = f"{key}_str"
                    new_value = str(value)
                    json["fields"][new_key] = new_value

                    if RE_DIGIT_TAIL.match(new_value):
                        json["fields"][key] = float(RE_DECIMAL.sub("", new_value))

                # Infinity and NaN are not valid floats in InfluxDB
                try:
                    if not math.isfinite(json["fields"][key]):
                        del json["fields"][key]
                except (KeyError, TypeError):
                    pass

        json["tags"].update(tags)

        return json

    instance = hass.data[DOMAIN] = InfluxThread(hass, influx, event_to_json, max_tries)
    instance.start()

    def shutdown(event):
        """Shut down the thread."""
        instance.queue.put(None)
        instance.join()
        influx.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True


class InfluxThread(threading.Thread):
    """A threaded event handler class."""

    def __init__(self, hass, influx, event_to_json, max_tries):
        """Initialize the listener."""
        threading.Thread.__init__(self, name="InfluxDB")
        self.queue = queue.Queue()
        self.influx = influx
        self.event_to_json = event_to_json
        self.max_tries = max_tries
        self.write_errors = 0
        self.shutdown = False
        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)

    def _event_listener(self, event):
        """Listen for new messages on the bus and queue them for Influx."""
        item = (time.monotonic(), event)
        self.queue.put(item)

    @staticmethod
    def batch_timeout():
        """Return number of seconds to wait for more events."""
        return BATCH_TIMEOUT

    def get_events_json(self):
        """Return a batch of events formatted for writing."""
        queue_seconds = QUEUE_BACKLOG_SECONDS + self.max_tries * RETRY_DELAY

        count = 0
        json = []

        dropped = 0

        try:
            while len(json) < BATCH_BUFFER_SIZE and not self.shutdown:
                timeout = None if count == 0 else self.batch_timeout()
                item = self.queue.get(timeout=timeout)
                count += 1

                if item is None:
                    self.shutdown = True
                else:
                    timestamp, event = item
                    age = time.monotonic() - timestamp

                    if age < queue_seconds:
                        event_json = self.event_to_json(event)
                        if event_json:
                            json.append(event_json)
                    else:
                        dropped += 1

        except queue.Empty:
            pass

        if dropped:
            _LOGGER.warning("Catching up, dropped %d old events", dropped)

        return count, json

    def write_to_influxdb(self, json):
        """Write preprocessed events to influxdb, with retry."""

        for retry in range(self.max_tries + 1):
            try:
                self.influx.write_points(json)

                if self.write_errors:
                    _LOGGER.error("Resumed, lost %d events", self.write_errors)
                    self.write_errors = 0

                _LOGGER.debug("Wrote %d events", len(json))
                break
            except (
                exceptions.InfluxDBClientError,
                exceptions.InfluxDBServerError,
                OSError,
            ) as err:
                if retry < self.max_tries:
                    time.sleep(RETRY_DELAY)
                else:
                    if not self.write_errors:
                        _LOGGER.error("Write error: %s", err)
                    self.write_errors += len(json)

    def run(self):
        """Process incoming events."""
        while not self.shutdown:
            count, json = self.get_events_json()
            if json:
                self.write_to_influxdb(json)
            for _ in range(count):
                self.queue.task_done()

    def block_till_done(self):
        """Block till all events processed."""
        self.queue.join()
