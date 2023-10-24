"""Tests for the TvOverlay integration."""
from unittest.mock import AsyncMock, patch

from homeassistant.components.tvoverlay.const import DEFAULT_NAME
from homeassistant.const import CONF_HOST, CONF_NAME

HOST = "0.0.0.0"
NAME = "Android Smart TV"

SERICVE_NAME = NAME.lower().replace(" ", "_")

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_DEFAULT_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: DEFAULT_NAME,
}


async def create_mocked_tv(raise_exception: bool = False) -> AsyncMock:
    """Create Mock TV for TvOVerlay Test."""
    mocked_tv = AsyncMock()
    mocked_tv.get_state = AsyncMock()
    return mocked_tv


def patch_config_flow_tv(mocked_tv: AsyncMock):
    """Create Config Patch for TvOVerlay Test."""
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications",
        return_value=mocked_tv,
    )


def mocked_tvoverlay_info():
    """Create mocked tvoverlay."""
    mocked_tvoverlay_info = {"result": {"settings": {"deviceName": NAME}}}
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications.async_connect",
        return_value=mocked_tvoverlay_info,
    )


def mocked_send_notification():
    """Create mocked tvoverlay."""
    mocked_tvoverlay_info = {"result": {"settings": {"deviceName": NAME}}}
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications.async_send",
        return_value=mocked_tvoverlay_info,
    )


def mocked_send_persistent_notification():
    """Create mocked tvoverlay."""
    mocked_tvoverlay_info = {"result": {"settings": {"deviceName": NAME}}}
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications.async_send_fixed",
        return_value=mocked_tvoverlay_info,
    )


def mocked_tvoverlay_default_info():
    """Create mocked tvoverlay with default name."""
    mocked_tvoverlay_info = {"result": {"settings": {"deviceName": DEFAULT_NAME}}}
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications.async_connect",
        return_value=mocked_tvoverlay_info,
    )
