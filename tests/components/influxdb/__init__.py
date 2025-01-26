"""Tests for the influxdb component."""

from homeassistant.components import influxdb

BASE_V1_CONFIG = {
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
BASE_V2_CONFIG = {
    "api_version": influxdb.API_VERSION_2,
    "host": "us-west-2-1.aws.cloud2.influxdata.com",
    "url": "https://us-west-2-1.aws.cloud2.influxdata.com",
    "token": "token",
    "organization": "org",
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
    "database": "home_assistant",
}


INFLUX_PATH = "homeassistant.components.influxdb"
INFLUX_CLIENT_PATH = f"{INFLUX_PATH}.InfluxDBClient"


def _get_write_api_mock_v1(mock_influx_client):
    """Return the write api mock for the V1 client."""
    return mock_influx_client.return_value.write_points


def _get_write_api_mock_v2(mock_influx_client):
    """Return the write api mock for the V2 client."""
    return mock_influx_client.return_value.write_api.return_value.write


def _split_config(conf):
    """Split the influxdb config into data and options."""
    data = {
        "api_version": conf.get("api_version"),
        "host": conf.get("host"),
        "port": conf.get("port"),
        "username": conf.get("username"),
        "password": conf.get("password"),
        "database": conf.get("database"),
        "token": conf.get("token"),
        "organization": conf.get("organization"),
        "bucket": conf.get("bucket"),
        "url": conf.get("url"),
        "ssl": conf.get("ssl"),
        "path": conf.get("path"),
        "verify_ssl": conf.get("verify_ssl"),
        "ssl_ca_cert": conf.get("ssl_ca_cert"),
    }

    options = {
        "max_retries": conf.get("max_retries"),
        "precision": conf.get("precision"),
        "measurement_attr": conf.get("measurement_attr"),
        "default_measurement": conf.get("default_measurement"),
        "override_measurement": conf.get("override_measurement"),
        "include": conf.get("include"),
        "exclude": conf.get("exclude"),
        "tags": conf.get("tags"),
        "tags_attributes": conf.get("tags_attributes"),
        "ignore_attributes": conf.get("ignore_attributes"),
        "component_config": conf.get("component_config"),
        "component_config_domain": conf.get("component_config_domain"),
        "component_config_glob": conf.get("component_config_glob"),
    }

    return {"data": data, "options": options}
