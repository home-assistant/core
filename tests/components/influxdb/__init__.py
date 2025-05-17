"""Tests for the influxdb component."""

from homeassistant.components import influxdb

BASE_V1_CONFIG = {
    "api_version": influxdb.DEFAULT_API_VERSION,
    "host": "localhost",
    "port": None,
    "username": None,
    "password": None,
    "ssl": None,
    "path": None,
    "database": "home_assistant",
    "verify_ssl": True,
    "ssl_ca_cert": None,
}
BASE_V2_CONFIG = {
    "api_version": influxdb.API_VERSION_2,
    "url": "https://us-west-2-1.aws.cloud2.influxdata.com",
    "token": "token",
    "organization": "org",
    "bucket": "Home Assistant",
    "verify_ssl": True,
    "ssl_ca_cert": None,
}
BASE_OPTIONS = {
    "max_retries": 0,
    "include": {
        "entity_globs": [],
        "entities": [],
        "domains": [],
    },
    "exclude": {
        "entity_globs": [],
        "entities": [],
        "domains": [],
    },
    "tags": {},
    "tags_attributes": [],
    "measurement_attr": "unit_of_measurement",
    "ignore_attributes": [],
    "component_config": {},
    "component_config_glob": {},
    "component_config_domain": {},
    "bucket": "Home Assistant",
}

INFLUX_PATH = "homeassistant.components.influxdb"
INFLUX_CLIENT_PATH = f"{INFLUX_PATH}.InfluxDBClient"


def _get_write_api_mock_v1(mock_influx_client):
    """Return the write api mock for the V1 client."""
    return mock_influx_client.return_value.write_points


def _get_write_api_mock_v2(mock_influx_client):
    """Return the write api mock for the V2 client."""
    return mock_influx_client.return_value.write_api.return_value.write
