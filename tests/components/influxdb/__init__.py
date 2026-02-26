"""Tests for the influxdb component."""

from homeassistant.components import influxdb
from homeassistant.components.influxdb import (
    CONF_API_VERSION,
    CONF_BUCKET,
    CONF_COMPONENT_CONFIG,
    CONF_COMPONENT_CONFIG_DOMAIN,
    CONF_COMPONENT_CONFIG_GLOB,
    CONF_DB_NAME,
    CONF_IGNORE_ATTRIBUTES,
    CONF_MEASUREMENT_ATTR,
    CONF_ORG,
    CONF_RETRY_COUNT,
    CONF_SSL_CA_CERT,
    CONF_TAGS,
    CONF_TAGS_ATTRIBUTES,
)
from homeassistant.const import (
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.entityfilter import (
    CONF_DOMAINS,
    CONF_ENTITIES,
    CONF_ENTITY_GLOBS,
)

BASE_V1_CONFIG = {
    CONF_API_VERSION: influxdb.DEFAULT_API_VERSION,
    CONF_HOST: "localhost",
    CONF_PORT: None,
    CONF_USERNAME: None,
    CONF_PASSWORD: None,
    CONF_SSL: None,
    CONF_PATH: None,
    CONF_DB_NAME: "home_assistant",
    CONF_VERIFY_SSL: True,
    CONF_SSL_CA_CERT: None,
}
BASE_V2_CONFIG = {
    CONF_API_VERSION: influxdb.API_VERSION_2,
    CONF_URL: "https://us-west-2-1.aws.cloud2.influxdata.com",
    CONF_TOKEN: "token",
    CONF_ORG: "org",
    CONF_BUCKET: "Home Assistant",
    CONF_VERIFY_SSL: True,
    CONF_SSL_CA_CERT: None,
}
BASE_OPTIONS = {
    CONF_RETRY_COUNT: 0,
    CONF_INCLUDE: {
        CONF_ENTITY_GLOBS: [],
        CONF_ENTITIES: [],
        CONF_DOMAINS: [],
    },
    CONF_EXCLUDE: {
        CONF_ENTITY_GLOBS: [],
        CONF_ENTITIES: [],
        CONF_DOMAINS: [],
    },
    CONF_TAGS: {},
    CONF_TAGS_ATTRIBUTES: [],
    CONF_MEASUREMENT_ATTR: "unit_of_measurement",
    CONF_IGNORE_ATTRIBUTES: [],
    CONF_COMPONENT_CONFIG: {},
    CONF_COMPONENT_CONFIG_GLOB: {},
    CONF_COMPONENT_CONFIG_DOMAIN: {},
    CONF_BUCKET: "Home Assistant",
}

INFLUX_PATH = "homeassistant.components.influxdb"
INFLUX_CLIENT_PATH = f"{INFLUX_PATH}.InfluxDBClient"


def _get_write_api_mock_v1(mock_influx_client):
    """Return the write api mock for the V1 client."""
    return mock_influx_client.return_value.write_points


def _get_write_api_mock_v2(mock_influx_client):
    """Return the write api mock for the V2 client."""
    return mock_influx_client.return_value.write_api.return_value.write
