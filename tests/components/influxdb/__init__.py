"""Tests for the influxdb component."""

from homeassistant.components import influxdb

BASE_V1_CONFIG = {
    "api_version": influxdb.DEFAULT_API_VERSION,
    "host": "host",
    "port": 123,
    "username": "user",
    "password": "password",
    "verify_ssl": "False",
    "ssl": "False",
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
    "verify_ssl": "True",
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
