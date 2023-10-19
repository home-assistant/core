"""Mock inputs for tests."""
from homeassistant.components.lamarzocco.const import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_PORT_LOCAL,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

MACHINE_NAME = "GS01234"
UNIQUE_ID = "1234"

DEFAULT_CONF = {
    "client_id": DEFAULT_CLIENT_ID,
    "client_secret": DEFAULT_CLIENT_SECRET,
    "port": DEFAULT_PORT_LOCAL,
}

USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_HOST: "192.168.1.42",
}

DISCOVERED_INFO = {
    CONF_NAME: "GS3_01234",
    CONF_MAC: "aa:bb:cc:dd:ee:ff",
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
    name="GS3_01234",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-63,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
)
