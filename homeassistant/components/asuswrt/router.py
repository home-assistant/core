"""Represent the AsusWrt router."""
from typing import Dict

from aioasuswrt.asuswrt import AsusWrt

from homeassistant.const import (
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)

from .const import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_REQUIRE_IP,
    CONF_SSH_KEY,
)


def get_api(conf: Dict) -> AsusWrt:
    """Get the AsusWrt API."""

    return AsusWrt(
        conf[CONF_HOST],
        conf[CONF_PORT],
        conf[CONF_PROTOCOL] == "telnet",
        conf[CONF_USERNAME],
        conf.get(CONF_PASSWORD, ""),
        conf.get(CONF_SSH_KEY, ""),
        conf[CONF_MODE],
        conf[CONF_REQUIRE_IP],
        interface=conf[CONF_INTERFACE],
        dnsmasq=conf[CONF_DNSMASQ],
    )
