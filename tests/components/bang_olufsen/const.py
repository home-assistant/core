"""Constants used for testing the bang_olufsen integration."""

from ipaddress import IPv4Address, IPv6Address

from homeassistant.components.bang_olufsen.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ITEM_NUMBER,
    ATTR_SERIAL_NUMBER,
    ATTR_TYPE_NUMBER,
    CONF_BEOLINK_JID,
)
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME

TEST_HOST = "192.168.0.1"
TEST_HOST_INVALID = "192.168.0"
TEST_HOST_IPV6 = "1111:2222:3333:4444:5555:6666:7777:8888"
TEST_MODEL_BALANCE = "Beosound Balance"
TEST_MODEL_THEATRE = "Beosound Theatre"
TEST_MODEL_LEVEL = "Beosound Level"
TEST_SERIAL_NUMBER = "11111111"
TEST_NAME = f"{TEST_MODEL_BALANCE}-{TEST_SERIAL_NUMBER}"
TEST_FRIENDLY_NAME = "Living room Balance"
TEST_TYPE_NUMBER = "1111"
TEST_ITEM_NUMBER = "1111111"
TEST_JID_1 = f"{TEST_TYPE_NUMBER}.{TEST_ITEM_NUMBER}.{TEST_SERIAL_NUMBER}@products.bang-olufsen.com"


TEST_HOSTNAME_ZEROCONF = TEST_NAME.replace(" ", "-") + ".local."
TEST_TYPE_ZEROCONF = "_bangolufsen._tcp.local."
TEST_NAME_ZEROCONF = TEST_NAME.replace(" ", "-") + "." + TEST_TYPE_ZEROCONF

TEST_DATA_USER = {CONF_HOST: TEST_HOST, CONF_MODEL: TEST_MODEL_BALANCE}
TEST_DATA_USER_INVALID = {CONF_HOST: TEST_HOST_INVALID, CONF_MODEL: TEST_MODEL_BALANCE}


TEST_DATA_CREATE_ENTRY = {
    CONF_HOST: TEST_HOST,
    CONF_MODEL: TEST_MODEL_BALANCE,
    CONF_BEOLINK_JID: TEST_JID_1,
    CONF_NAME: TEST_NAME,
}

TEST_DATA_ZEROCONF = ZeroconfServiceInfo(
    ip_address=IPv4Address(TEST_HOST),
    ip_addresses=[IPv4Address(TEST_HOST)],
    port=80,
    hostname=TEST_HOSTNAME_ZEROCONF,
    type=TEST_TYPE_ZEROCONF,
    name=TEST_NAME_ZEROCONF,
    properties={
        ATTR_FRIENDLY_NAME: TEST_FRIENDLY_NAME,
        ATTR_SERIAL_NUMBER: TEST_SERIAL_NUMBER,
        ATTR_TYPE_NUMBER: TEST_TYPE_NUMBER,
        ATTR_ITEM_NUMBER: TEST_ITEM_NUMBER,
    },
)

TEST_DATA_ZEROCONF_NOT_MOZART = ZeroconfServiceInfo(
    ip_address=IPv4Address(TEST_HOST),
    ip_addresses=[IPv4Address(TEST_HOST)],
    port=80,
    hostname=TEST_HOSTNAME_ZEROCONF,
    type=TEST_TYPE_ZEROCONF,
    name=TEST_NAME_ZEROCONF,
    properties={ATTR_SERIAL_NUMBER: TEST_SERIAL_NUMBER},
)

TEST_DATA_ZEROCONF_IPV6 = ZeroconfServiceInfo(
    ip_address=IPv6Address(TEST_HOST_IPV6),
    ip_addresses=[IPv6Address(TEST_HOST_IPV6)],
    port=80,
    hostname=TEST_HOSTNAME_ZEROCONF,
    type=TEST_TYPE_ZEROCONF,
    name=TEST_NAME_ZEROCONF,
    properties={
        ATTR_FRIENDLY_NAME: TEST_FRIENDLY_NAME,
        ATTR_SERIAL_NUMBER: TEST_SERIAL_NUMBER,
        ATTR_TYPE_NUMBER: TEST_TYPE_NUMBER,
        ATTR_ITEM_NUMBER: TEST_ITEM_NUMBER,
    },
)
