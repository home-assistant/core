"""Common stuff for AVM Fritz!Box tests."""
from homeassistant.components import ssdp
from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.ssdp import ATTR_UPNP_FRIENDLY_NAME, ATTR_UPNP_UDN
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

ATTR_HOST = "host"
ATTR_NEW_SERIAL_NUMBER = "NewSerialNumber"

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PORT: "1234",
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
            }
        ]
    }
}
MOCK_HOST = "fake_host"
MOCK_IP = "192.168.178.1"
MOCK_SERIAL_NUMBER = "fake_serial_number"
MOCK_FIRMWARE_INFO = [True, "1.1.1"]

MOCK_USER_DATA = MOCK_CONFIG[DOMAIN][CONF_DEVICES][0]
MOCK_DEVICE_INFO = {
    ATTR_HOST: MOCK_HOST,
    ATTR_NEW_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
}
MOCK_SSDP_DATA = ssdp.SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"https://{MOCK_IP}:12345/test",
    upnp={
        ATTR_UPNP_FRIENDLY_NAME: "fake_name",
        ATTR_UPNP_UDN: "uuid:only-a-test",
    },
)

MOCK_REQUEST = b'<?xml version="1.0" encoding="utf-8"?><SessionInfo><SID>xxxxxxxxxxxxxxxx</SID><Challenge>xxxxxxxx</Challenge><BlockTime>0</BlockTime><Rights><Name>Dial</Name><Access>2</Access><Name>App</Name><Access>2</Access><Name>HomeAuto</Name><Access>2</Access><Name>BoxAdmin</Name><Access>2</Access><Name>Phone</Name><Access>2</Access><Name>NAS</Name><Access>2</Access></Rights><Users><User last="1">FakeFritzUser</User></Users></SessionInfo>\n'
