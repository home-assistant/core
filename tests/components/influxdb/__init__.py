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


# def _split_config(conf):
#     """Split the influxdb config into data and options."""
#     api_version = conf.get("api_version")
#     if api_version == influxdb.DEFAULT_API_VERSION:
#         data = {
#             "api_version": conf.get("api_version"),
#             "host": conf.get("host"),
#             "port": conf.get("port"),
#             "username": conf.get("username"),
#             "password": conf.get("password"),
#             "database": conf.get("database"),
#             "ssl": conf.get("ssl"),
#             "path": conf.get("path"),
#             "verify_ssl": conf.get("verify_ssl"),
#             "ssl_ca_cert": conf.get("ssl_ca_cert"),
#         }
#     else:
#         url = conf["host"]
#         if conf.get("ssl"):
#             url = f"https://{url}"
#         else:
#             url = f"http://{url}"

#         if conf.get("port"):
#             url = f"{url}:{conf['port']}"

#         if conf.get("path"):
#             url = f"{url}{conf['path']}"

#         data = {
#             "api_version": conf["api_version"],
#             "token": conf["token"],
#             "organization": conf["organization"],
#             "bucket": conf["bucket"],
#             "verify_ssl": conf.get("verify_ssl"),
#             "ssl_ca_cert": conf.get("ssl_ca_cert"),
#             "url": url,
#         }

#     options = {
#         "max_retries": conf.get("max_retries"),
#         "precision": conf.get("precision"),
#         "measurement_attr": conf.get("measurement_attr"),
#         "default_measurement": conf.get("default_measurement"),
#         "override_measurement": conf.get("override_measurement"),
#         "include": conf.get("include"),
#         "exclude": conf.get("exclude"),
#         "tags": conf.get("tags"),
#         "tags_attributes": conf.get("tags_attributes"),
#         "ignore_attributes": conf.get("ignore_attributes"),
#         "component_config": conf.get("component_config"),
#         "component_config_domain": conf.get("component_config_domain"),
#         "component_config_glob": conf.get("component_config_glob"),
#     }

#     return {"data": data, "options": options}
