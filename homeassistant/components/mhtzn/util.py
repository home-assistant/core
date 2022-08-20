"""Utility functions for the MHTZN integration."""

from homeassistant.const import CONF_NAME, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_PROTOCOL

from .const import CONF_BROKER


def get_connection_name(discovery_info):
    """Parse mdns data to obtain gateway name"""

    service_type = discovery_info.type[:-1]
    return discovery_info.name.replace(f".{service_type}.", "")


def format_connection(discovery_info):
    """Parse and format mdns data"""

    name = get_connection_name(discovery_info)
    host = discovery_info.host
    port = discovery_info.port
    username = None
    password = None

    for key, value in discovery_info.properties.items():
        if key == 'username':
            username = value
        elif key == 'password':
            password = value
        elif key == 'host':
            host = value

    connection = {
        CONF_NAME: name,
        CONF_BROKER: host,
        CONF_PORT: port,
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
        CONF_PROTOCOL: "3.1.1",
        "keepalive": 60
    }

    return connection

