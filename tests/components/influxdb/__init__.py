"""Tests for the influxdb component."""

from homeassistant.components import influxdb

BASE_V1_CONFIG = {
    "api_version": influxdb.DEFAULT_API_VERSION,
    "host": "host",
    "port": 123,
    "username": "user",
    "password": "password",
    "verify_ssl": False,
    "ssl": False,
    "database": "db",
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
}
BASE_V2_CONFIG = {
    "api_version": influxdb.API_VERSION_2,
    "host": "host",
    "port": 123,
    "token": "token",
    "organization": "organization",
    "bucket": "Home Assistant",
    "verify_ssl": True,
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
    "max_retries": 0,
    "tags": {},
    "tags_attributes": [],
    "measurement_attr": "unit_of_measurement",
    "ignore_attributes": [],
    "component_config": {},
    "component_config_glob": {},
    "component_config_domain": {},
}

IMPORT_V1_CONFIG = {
    "api_version": influxdb.DEFAULT_API_VERSION,
    "host": "localhost",
    "verify_ssl": True,
    "database": "home_assistant",
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
IMPORT_V2_CONFIG = {
    "api_version": influxdb.API_VERSION_2,
    "host": "us-west-2-1.aws.cloud2.influxdata.com",
    "url": "https://us-west-2-1.aws.cloud2.influxdata.com",
    "token": "token",
    "organization": "org",
    "database": "home_assistant",
    "bucket": "Home Assistant",
    "verify_ssl": True,
    "ssl": True,
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
    "max_retries": 0,
    "tags": {},
    "tags_attributes": [],
    "measurement_attr": "unit_of_measurement",
    "ignore_attributes": [],
    "component_config": {},
    "component_config_glob": {},
    "component_config_domain": {},
}


INFLUX_PATH = "homeassistant.components.influxdb"
INFLUX_CLIENT_PATH = f"{INFLUX_PATH}.InfluxDBClient"


def _get_write_api_mock_v1(mock_influx_client):
    """Return the write api mock for the V1 client."""
    return mock_influx_client.return_value.write_points


def _get_write_api_mock_v2(mock_influx_client):
    """Return the write api mock for the V2 client."""
    return mock_influx_client.return_value.write_api.return_value.write
