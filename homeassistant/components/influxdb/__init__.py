"""Support for sending data to an Influx database."""
from dataclasses import dataclass
import logging
import math
import queue
import threading
import time
from typing import Any, Callable, Dict, List

from influxdb import InfluxDBClient, exceptions
from influxdb_client import InfluxDBClient as InfluxDBClientV2
from influxdb_client.client.write_api import ASYNCHRONOUS, SYNCHRONOUS
from influxdb_client.rest import ApiException
import requests.exceptions
import urllib3.exceptions
import voluptuous as vol

from homeassistant.const import (
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import event as event_helper, state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
)

from .const import (
    API_VERSION_2,
    BATCH_BUFFER_SIZE,
    BATCH_TIMEOUT,
    CATCHING_UP_MESSAGE,
    CLIENT_ERROR_V1,
    CLIENT_ERROR_V2,
    CODE_INVALID_INPUTS,
    COMPONENT_CONFIG_SCHEMA_CONNECTION,
    CONF_API_VERSION,
    CONF_BUCKET,
    CONF_COMPONENT_CONFIG,
    CONF_COMPONENT_CONFIG_DOMAIN,
    CONF_COMPONENT_CONFIG_GLOB,
    CONF_DB_NAME,
    CONF_DEFAULT_MEASUREMENT,
    CONF_HOST,
    CONF_IGNORE_ATTRIBUTES,
    CONF_MEASUREMENT_ATTR,
    CONF_ORG,
    CONF_OVERRIDE_MEASUREMENT,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_PRECISION,
    CONF_RETRY_COUNT,
    CONF_SSL,
    CONF_SSL_CA_CERT,
    CONF_TAGS,
    CONF_TAGS_ATTRIBUTES,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONNECTION_ERROR,
    DEFAULT_API_VERSION,
    DEFAULT_HOST_V2,
    DEFAULT_MEASUREMENT_ATTR,
    DEFAULT_SSL_V2,
    DOMAIN,
    EVENT_NEW_STATE,
    INFLUX_CONF_FIELDS,
    INFLUX_CONF_MEASUREMENT,
    INFLUX_CONF_ORG,
    INFLUX_CONF_STATE,
    INFLUX_CONF_TAGS,
    INFLUX_CONF_TIME,
    INFLUX_CONF_VALUE,
    QUERY_ERROR,
    QUEUE_BACKLOG_SECONDS,
    RE_DECIMAL,
    RE_DIGIT_TAIL,
    RESUMED_MESSAGE,
    RETRY_DELAY,
    RETRY_INTERVAL,
    RETRY_MESSAGE,
    TEST_QUERY_V1,
    TEST_QUERY_V2,
    TIMEOUT,
    WRITE_ERROR,
    WROTE_MESSAGE,
)

_LOGGER = logging.getLogger(__name__)


def create_influx_url(conf: Dict) -> Dict:
    """Build URL used from config inputs and default when necessary."""
    if conf[CONF_API_VERSION] == API_VERSION_2:
        if CONF_SSL not in conf:
            conf[CONF_SSL] = DEFAULT_SSL_V2
        if CONF_HOST not in conf:
            conf[CONF_HOST] = DEFAULT_HOST_V2

        url = conf[CONF_HOST]
        if conf[CONF_SSL]:
            url = f"https://{url}"
        else:
            url = f"http://{url}"

        if CONF_PORT in conf:
            url = f"{url}:{conf[CONF_PORT]}"

        if CONF_PATH in conf:
            url = f"{url}{conf[CONF_PATH]}"

        conf[CONF_URL] = url

    return conf


def validate_version_specific_config(conf: Dict) -> Dict:
    """Ensure correct config fields are provided based on API version used."""
    if conf[CONF_API_VERSION] == API_VERSION_2:
        if CONF_TOKEN not in conf:
            raise vol.Invalid(
                f"{CONF_TOKEN} and {CONF_BUCKET} are required when {CONF_API_VERSION} is {API_VERSION_2}"
            )

        if CONF_USERNAME in conf:
            raise vol.Invalid(
                f"{CONF_USERNAME} and {CONF_PASSWORD} are only allowed when {CONF_API_VERSION} is {DEFAULT_API_VERSION}"
            )

    else:
        if CONF_TOKEN in conf:
            raise vol.Invalid(
                f"{CONF_TOKEN} and {CONF_BUCKET} are only allowed when {CONF_API_VERSION} is {API_VERSION_2}"
            )

    return conf


_CUSTOMIZE_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string,
        vol.Optional(CONF_IGNORE_ATTRIBUTES): vol.All(cv.ensure_list, [cv.string]),
    }
)

_INFLUX_BASE_SCHEMA = INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA.extend(
    {
        vol.Optional(CONF_RETRY_COUNT, default=0): cv.positive_int,
        vol.Optional(CONF_DEFAULT_MEASUREMENT): cv.string,
        vol.Optional(CONF_MEASUREMENT_ATTR, default=DEFAULT_MEASUREMENT_ATTR): vol.In(
            ["unit_of_measurement", "domain__device_class", "entity_id"]
        ),
        vol.Optional(CONF_OVERRIDE_MEASUREMENT): cv.string,
        vol.Optional(CONF_TAGS, default={}): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_TAGS_ATTRIBUTES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_IGNORE_ATTRIBUTES, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_COMPONENT_CONFIG, default={}): vol.Schema(
            {cv.entity_id: _CUSTOMIZE_ENTITY_SCHEMA}
        ),
        vol.Optional(CONF_COMPONENT_CONFIG_GLOB, default={}): vol.Schema(
            {cv.string: _CUSTOMIZE_ENTITY_SCHEMA}
        ),
        vol.Optional(CONF_COMPONENT_CONFIG_DOMAIN, default={}): vol.Schema(
            {cv.string: _CUSTOMIZE_ENTITY_SCHEMA}
        ),
    }
)

INFLUX_SCHEMA = vol.All(
    _INFLUX_BASE_SCHEMA.extend(COMPONENT_CONFIG_SCHEMA_CONNECTION),
    validate_version_specific_config,
    create_influx_url,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: INFLUX_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)


def _generate_event_to_json(conf: Dict) -> Callable[[Dict], str]:
    """Build event to json converter and add to config."""
    entity_filter = convert_include_exclude_filter(conf)
    tags = conf.get(CONF_TAGS)
    tags_attributes = conf.get(CONF_TAGS_ATTRIBUTES)
    default_measurement = conf.get(CONF_DEFAULT_MEASUREMENT)
    measurement_attr = conf.get(CONF_MEASUREMENT_ATTR)
    override_measurement = conf.get(CONF_OVERRIDE_MEASUREMENT)
    global_ignore_attributes = set(conf[CONF_IGNORE_ATTRIBUTES])
    component_config = EntityValues(
        conf[CONF_COMPONENT_CONFIG],
        conf[CONF_COMPONENT_CONFIG_DOMAIN],
        conf[CONF_COMPONENT_CONFIG_GLOB],
    )

    def event_to_json(event: Dict) -> str:
        """Convert event into json in format Influx expects."""
        state = event.data.get(EVENT_NEW_STATE)
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not entity_filter(state.entity_id)
        ):
            return

        try:
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
        include_dc = True
        entity_config = component_config.get(state.entity_id)
        measurement = entity_config.get(CONF_OVERRIDE_MEASUREMENT)
        if measurement in (None, ""):
            if override_measurement:
                measurement = override_measurement
            else:
                if measurement_attr == "entity_id":
                    measurement = state.entity_id
                elif measurement_attr == "domain__device_class":
                    device_class = state.attributes.get("device_class")
                    if device_class is None:
                        # This entity doesn't have a device_class set, use only domain
                        measurement = state.domain
                    else:
                        measurement = f"{state.domain}__{device_class}"
                        include_dc = False
                else:
                    measurement = state.attributes.get(measurement_attr)
                if measurement in (None, ""):
                    if default_measurement:
                        measurement = default_measurement
                    else:
                        measurement = state.entity_id
                else:
                    include_uom = measurement_attr != "unit_of_measurement"

        json = {
            INFLUX_CONF_MEASUREMENT: measurement,
            INFLUX_CONF_TAGS: {
                CONF_DOMAIN: state.domain,
                CONF_ENTITY_ID: state.object_id,
            },
            INFLUX_CONF_TIME: event.time_fired,
            INFLUX_CONF_FIELDS: {},
        }
        if _include_state:
            json[INFLUX_CONF_FIELDS][INFLUX_CONF_STATE] = state.state
        if _include_value:
            json[INFLUX_CONF_FIELDS][INFLUX_CONF_VALUE] = _state_as_value

        ignore_attributes = set(entity_config.get(CONF_IGNORE_ATTRIBUTES, []))
        ignore_attributes.update(global_ignore_attributes)
        for key, value in state.attributes.items():
            if key in tags_attributes:
                json[INFLUX_CONF_TAGS][key] = value
            elif (
                (key != CONF_UNIT_OF_MEASUREMENT or include_uom)
                and (key != "device_class" or include_dc)
                and key not in ignore_attributes
            ):
                # If the key is already in fields
                if key in json[INFLUX_CONF_FIELDS]:
                    key = f"{key}_"
                # Prevent column data errors in influxDB.
                # For each value we try to cast it as float
                # But if we can not do it we store the value
                # as string add "_str" postfix to the field key
                try:
                    json[INFLUX_CONF_FIELDS][key] = float(value)
                except (ValueError, TypeError):
                    new_key = f"{key}_str"
                    new_value = str(value)
                    json[INFLUX_CONF_FIELDS][new_key] = new_value

                    if RE_DIGIT_TAIL.match(new_value):
                        json[INFLUX_CONF_FIELDS][key] = float(
                            RE_DECIMAL.sub("", new_value)
                        )

                # Infinity and NaN are not valid floats in InfluxDB
                try:
                    if not math.isfinite(json[INFLUX_CONF_FIELDS][key]):
                        del json[INFLUX_CONF_FIELDS][key]
                except (KeyError, TypeError):
                    pass

        json[INFLUX_CONF_TAGS].update(tags)

        return json

    return event_to_json


@dataclass
class InfluxClient:
    """An InfluxDB client wrapper for V1 or V2."""

    data_repositories: List[str]
    write: Callable[[str], None]
    query: Callable[[str, str], List[Any]]
    close: Callable[[], None]


def get_influx_connection(conf, test_write=False, test_read=False):
    """Create the correct influx connection for the API version."""
    kwargs = {
        CONF_TIMEOUT: TIMEOUT,
    }
    precision = conf.get(CONF_PRECISION)

    if conf[CONF_API_VERSION] == API_VERSION_2:
        kwargs[CONF_URL] = conf[CONF_URL]
        kwargs[CONF_TOKEN] = conf[CONF_TOKEN]
        kwargs[INFLUX_CONF_ORG] = conf[CONF_ORG]
        kwargs[CONF_VERIFY_SSL] = conf[CONF_VERIFY_SSL]
        if CONF_SSL_CA_CERT in conf:
            kwargs[CONF_SSL_CA_CERT] = conf[CONF_SSL_CA_CERT]
        bucket = conf.get(CONF_BUCKET)
        influx = InfluxDBClientV2(**kwargs)
        query_api = influx.query_api()
        initial_write_mode = SYNCHRONOUS if test_write else ASYNCHRONOUS
        write_api = influx.write_api(write_options=initial_write_mode)

        def write_v2(json):
            """Write data to V2 influx."""
            data = {"bucket": bucket, "record": json}

            if precision is not None:
                data["write_precision"] = precision

            try:
                write_api.write(**data)
            except (urllib3.exceptions.HTTPError, OSError) as exc:
                raise ConnectionError(CONNECTION_ERROR % exc) from exc
            except ApiException as exc:
                if exc.status == CODE_INVALID_INPUTS:
                    raise ValueError(WRITE_ERROR % (json, exc)) from exc
                raise ConnectionError(CLIENT_ERROR_V2 % exc) from exc

        def query_v2(query, _=None):
            """Query V2 influx."""
            try:
                return query_api.query(query)
            except (urllib3.exceptions.HTTPError, OSError) as exc:
                raise ConnectionError(CONNECTION_ERROR % exc) from exc
            except ApiException as exc:
                if exc.status == CODE_INVALID_INPUTS:
                    raise ValueError(QUERY_ERROR % (query, exc)) from exc
                raise ConnectionError(CLIENT_ERROR_V2 % exc) from exc

        def close_v2():
            """Close V2 influx client."""
            influx.close()

        buckets = []
        if test_write:
            # Try to write b"" to influx. If we can connect and creds are valid
            # Then invalid inputs is returned. Anything else is a broken config
            try:
                write_v2(b"")
            except ValueError:
                pass
            write_api = influx.write_api(write_options=ASYNCHRONOUS)

        if test_read:
            tables = query_v2(TEST_QUERY_V2)
            if tables and tables[0].records:
                buckets = [bucket.values["name"] for bucket in tables[0].records]
            else:
                buckets = []

        return InfluxClient(buckets, write_v2, query_v2, close_v2)

    # Else it's a V1 client
    if CONF_SSL_CA_CERT in conf and conf[CONF_VERIFY_SSL]:
        kwargs[CONF_VERIFY_SSL] = conf[CONF_SSL_CA_CERT]
    else:
        kwargs[CONF_VERIFY_SSL] = conf[CONF_VERIFY_SSL]

    if CONF_DB_NAME in conf:
        kwargs[CONF_DB_NAME] = conf[CONF_DB_NAME]

    if CONF_USERNAME in conf:
        kwargs[CONF_USERNAME] = conf[CONF_USERNAME]

    if CONF_PASSWORD in conf:
        kwargs[CONF_PASSWORD] = conf[CONF_PASSWORD]

    if CONF_HOST in conf:
        kwargs[CONF_HOST] = conf[CONF_HOST]

    if CONF_PATH in conf:
        kwargs[CONF_PATH] = conf[CONF_PATH]

    if CONF_PORT in conf:
        kwargs[CONF_PORT] = conf[CONF_PORT]

    if CONF_SSL in conf:
        kwargs[CONF_SSL] = conf[CONF_SSL]

    influx = InfluxDBClient(**kwargs)

    def write_v1(json):
        """Write data to V1 influx."""
        try:
            influx.write_points(json, time_precision=precision)
        except (
            requests.exceptions.RequestException,
            exceptions.InfluxDBServerError,
            OSError,
        ) as exc:
            raise ConnectionError(CONNECTION_ERROR % exc) from exc
        except exceptions.InfluxDBClientError as exc:
            if exc.code == CODE_INVALID_INPUTS:
                raise ValueError(WRITE_ERROR % (json, exc)) from exc
            raise ConnectionError(CLIENT_ERROR_V1 % exc) from exc

    def query_v1(query, database=None):
        """Query V1 influx."""
        try:
            return list(influx.query(query, database=database).get_points())
        except (
            requests.exceptions.RequestException,
            exceptions.InfluxDBServerError,
            OSError,
        ) as exc:
            raise ConnectionError(CONNECTION_ERROR % exc) from exc
        except exceptions.InfluxDBClientError as exc:
            if exc.code == CODE_INVALID_INPUTS:
                raise ValueError(QUERY_ERROR % (query, exc)) from exc
            raise ConnectionError(CLIENT_ERROR_V1 % exc) from exc

    def close_v1():
        """Close the V1 Influx client."""
        influx.close()

    databases = []
    if test_write:
        write_v1([])

    if test_read:
        databases = [db["name"] for db in query_v1(TEST_QUERY_V1)]

    return InfluxClient(databases, write_v1, query_v1, close_v1)


def setup(hass, config):
    """Set up the InfluxDB component."""
    conf = config[DOMAIN]
    try:
        influx = get_influx_connection(conf, test_write=True)
    except ConnectionError as exc:
        _LOGGER.error(RETRY_MESSAGE, exc)
        event_helper.call_later(hass, RETRY_INTERVAL, lambda _: setup(hass, config))
        return True

    event_to_json = _generate_event_to_json(conf)
    max_tries = conf.get(CONF_RETRY_COUNT)
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
        threading.Thread.__init__(self, name=DOMAIN)
        self.queue = queue.Queue()
        self.influx = influx
        self.event_to_json = event_to_json
        self.max_tries = max_tries
        self.write_errors = 0
        self.shutdown = False
        hass.bus.listen(EVENT_STATE_CHANGED, self._event_listener)

    @callback
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
            _LOGGER.warning(CATCHING_UP_MESSAGE, dropped)

        return count, json

    def write_to_influxdb(self, json):
        """Write preprocessed events to influxdb, with retry."""
        for retry in range(self.max_tries + 1):
            try:
                self.influx.write(json)

                if self.write_errors:
                    _LOGGER.error(RESUMED_MESSAGE, self.write_errors)
                    self.write_errors = 0

                _LOGGER.debug(WROTE_MESSAGE, len(json))
                break
            except ValueError as err:
                _LOGGER.error(err)
                break
            except ConnectionError as err:
                if retry < self.max_tries:
                    time.sleep(RETRY_DELAY)
                else:
                    if not self.write_errors:
                        _LOGGER.error(err)
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
