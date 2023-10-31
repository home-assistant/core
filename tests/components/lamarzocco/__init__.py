"""Mock inputs for tests."""
from homeassistant.components.lamarzocco.const import (
    CONF_MACHINE,
    CONF_USE_BLUETOOTH,
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_PORT_LOCAL,
    SERIAL_NUMBER,
)
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

MACHINE_NAME = "GS01234"
UNIQUE_ID = "1234"

DEFAULT_CONF = {
    CONF_CLIENT_ID: DEFAULT_CLIENT_ID,
    CONF_CLIENT_SECRET: DEFAULT_CLIENT_SECRET,
    CONF_PORT: DEFAULT_PORT_LOCAL,
}

USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

MACHINE_DATA = {
    CONF_HOST: "192.168.1.1",
    CONF_MACHINE: "GS3 AV (GS01234)",
    SERIAL_NUMBER: "GS01234",
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

MACHINE_SELECTION = {
    CONF_MACHINE: "GS3 AV (GS01234)",
    CONF_HOST: "192.168.1.1",
}

OPTIONS_INPUT = {CONF_HOST: "192.168.1.42", CONF_USE_BLUETOOTH: False}

LM_SERVICE_INFO = BluetoothServiceInfo(
    name="GS3_01234",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-63,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
)
