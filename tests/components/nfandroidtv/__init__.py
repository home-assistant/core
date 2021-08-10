"""Tests for the NFAndroidTV integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS, MAC_ADDRESS
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import format_mac

HOST = "1.2.3.4"
NAME = "Android TV / Fire TV"

CONF_DATA = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_DHCP_FLOW_FIRE_TV = {
    IP_ADDRESS: "1.1.1.1",
    MAC_ADDRESS: format_mac("AA:BB:CC:DD:EE:FF"),
    HOSTNAME: "amazon-fffffffff",
}

CONF_DHCP_FLOW_ANDROID_TV = {
    IP_ADDRESS: "1.1.1.1",
    MAC_ADDRESS: format_mac("AA:BB:CC:DD:EE:FF"),
    HOSTNAME: "any",
}


async def _create_mocked_tv(raise_exception=False):
    mocked_tv = AsyncMock()
    mocked_tv.get_state = AsyncMock()
    return mocked_tv


def _patch_config_flow_tv(mocked_tv):
    return patch(
        "homeassistant.components.nfandroidtv.config_flow.Notifications",
        return_value=mocked_tv,
    )
