"""Constants for InfluxDB integration."""
from datetime import timedelta
import re

import voluptuous as vol

from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv

CONF_DB_NAME = "database"
CONF_BUCKET = "bucket"
CONF_ORG = "organization"
CONF_TAGS = "tags"
CONF_DEFAULT_MEASUREMENT = "default_measurement"
CONF_OVERRIDE_MEASUREMENT = "override_measurement"
CONF_TAGS_ATTRIBUTES = "tags_attributes"
CONF_COMPONENT_CONFIG = "component_config"
CONF_COMPONENT_CONFIG_GLOB = "component_config_glob"
CONF_COMPONENT_CONFIG_DOMAIN = "component_config_domain"
CONF_RETRY_COUNT = "max_retries"

CONF_LANGUAGE = "language"
CONF_QUERIES = "queries"
CONF_QUERIES_FLUX = "queries_flux"
CONF_GROUP_FUNCTION = "group_function"
CONF_FIELD = "field"
CONF_MEASUREMENT_NAME = "measurement"
CONF_WHERE = "where"

CONF_RANGE_START = "range_start"
CONF_RANGE_STOP = "range_stop"
CONF_FUNCTION = "function"
CONF_QUERY = "query"
CONF_IMPORTS = "imports"

DEFAULT_DATABASE = "home_assistant"
DEFAULT_HOST_V2 = "us-west-2-1.aws.cloud2.influxdata.com"
DEFAULT_SSL_V2 = True
DEFAULT_BUCKET = "Home Assistant"
DEFAULT_VERIFY_SSL = True
DEFAULT_API_VERSION = "1"
DEFAULT_GROUP_FUNCTION = "mean"
DEFAULT_FIELD = "value"
DEFAULT_RANGE_START = "-15m"
DEFAULT_RANGE_STOP = "now()"

DOMAIN = "influxdb"
API_VERSION_2 = "2"
TIMEOUT = 5
RETRY_DELAY = 20
QUEUE_BACKLOG_SECONDS = 30
RETRY_INTERVAL = 60  # seconds
BATCH_TIMEOUT = 1
BATCH_BUFFER_SIZE = 100
LANGUAGE_INFLUXQL = "influxQL"
LANGUAGE_FLUX = "flux"
TEST_QUERY_V1 = "SHOW SERIES LIMIT 1;"
TEST_QUERY_V2 = "buckets() |> limit(n:1)"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

RE_DIGIT_TAIL = re.compile(r"^[^\.]*\d+\.?\d+[^\.]*$")
RE_DECIMAL = re.compile(r"[^\d.]+")

CONNECTION_ERROR = (
    "Cannot connect to InfluxDB due to '%s'. "
    "Please check that the provided connection details (host, port, etc.) are correct "
    "and that your InfluxDB server is running and accessible."
)
CLIENT_ERROR_V2 = (
    "InfluxDB bucket is not accessible due to '%s'. "
    "Please check that the bucket, org and token are correct and "
    "that the token has the correct permissions set."
)
CLIENT_ERROR_V1 = (
    "InfluxDB database is not accessible due to '%s'. "
    "Please check that the database, username and password are correct and "
    "that the specified user has the correct permissions set."
)
WRITE_ERROR = "Could not write '%s' to influx due to '%s'."
QUERY_ERROR = (
    "Could not execute query '%s' due to '%s'. Check the syntax of your query."
)
RETRY_MESSAGE = f"Retrying again in {RETRY_INTERVAL} seconds."
CONNECTION_ERROR_WITH_RETRY = f"{CONNECTION_ERROR} {RETRY_MESSAGE}"
CLIENT_ERROR_V1_WITH_RETRY = f"{CLIENT_ERROR_V1} {RETRY_MESSAGE}"
CLIENT_ERROR_V2_WITH_RETRY = f"{CLIENT_ERROR_V2} {RETRY_MESSAGE}"


COMPONENT_CONFIG_SCHEMA_CONNECTION = {
    # Connection config for V1 and V2 APIs.
    vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): vol.All(
        vol.Coerce(str), vol.In([DEFAULT_API_VERSION, API_VERSION_2]),
    ),
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PATH): cv.string,
    vol.Optional(CONF_PORT): cv.port,
    vol.Optional(CONF_SSL): cv.boolean,
    # Connection config for V1 API only.
    vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
    vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
    vol.Optional(CONF_DB_NAME, default=DEFAULT_DATABASE): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    # Connection config for V2 API only.
    vol.Inclusive(CONF_TOKEN, "v2_authentication"): cv.string,
    vol.Inclusive(CONF_ORG, "v2_authentication"): cv.string,
    vol.Optional(CONF_BUCKET, default=DEFAULT_BUCKET): cv.string,
}
