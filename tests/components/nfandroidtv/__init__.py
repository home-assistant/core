"""Tests for the NFAndroidTV integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import format_mac

from tests.test_util.aiohttp import AiohttpClientMocker

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

CONF_DHCP_FLOW_FIRE_TV = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="amazon-fffffffff",
    macaddress=format_mac("AA:BB:CC:DD:EE:FF"),
)

CONF_DHCP_FLOW_ANDROID_TV = DhcpServiceInfo(
    ip="1.1.1.1", hostname="any", macaddress=format_mac("AA:BB:CC:DD:EE:FF")
)


async def _create_mocked_tv():
    mocked_tv = AsyncMock()
    mocked_tv.get_state = AsyncMock()
    return mocked_tv


def _patch_config_flow_tv(mocked_tv):
    return patch(
        "homeassistant.components.nfandroidtv.config_flow.Notifications",
        return_value=mocked_tv,
    )


async def mock_response(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Mock response from Android TV."""
    aioclient_mock.get(
        "http://1.1.1.1:8009",
        text="Error 400, Bad Request.",
    )
