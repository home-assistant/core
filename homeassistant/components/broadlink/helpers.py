"""Helper functions for the Broadlink integration."""
from base64 import b64decode

import homeassistant.helpers.config_validation as cv


def data_packet(value):
    """Decode a data packet given for a Broadlink remote."""
    value = cv.string(value)
    extra = len(value) % 4
    if extra > 0:
        value = value + ("=" * (4 - extra))
    return b64decode(value)


def mac_address(value):
    """Validate a MAC address."""
    mac = str(value).lower()
    if len(mac) == 17:
        mac = mac[0:2] + mac[3:5] + mac[6:8] + mac[9:11] + mac[12:14] + mac[15:17]
    elif len(mac) == 14:
        mac = mac[0:2] + mac[2:4] + mac[5:7] + mac[7:9] + mac[10:12] + mac[12:14]
    elif len(mac) != 12:
        raise ValueError
    return mac
