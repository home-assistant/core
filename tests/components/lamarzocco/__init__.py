"""Mock inputs for tests."""
from homeassistant.components.lamarzocco.const import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_PORT_LOCAL,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

MACHINE_NAME = "GS01234"
UNIQUE_ID = "1234"

DEFAULT_CONF = {
    "client_id": DEFAULT_CLIENT_ID,
    "client_secret": DEFAULT_CLIENT_SECRET,
    "machine_name": MACHINE_NAME,
    "port": DEFAULT_PORT_LOCAL,
    "title": MACHINE_NAME,
}

USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_HOST: "192.168.1.42",
}

LOGIN_INFO = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

WRONG_LOGIN_INFO = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "wrong_password",
}

LM_SERVICE_INFO = BluetoothServiceInfo(
    name="MICRA_123532",
    address="11:22:33:44:55",
    rssi=-63,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
)
