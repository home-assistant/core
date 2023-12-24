"""Tests for the TvOverlay integration."""
from unittest.mock import patch

from homeassistant.components.tvoverlay.const import DEFAULT_NAME
from homeassistant.const import CONF_HOST, CONF_NAME

HOST = "0.0.0.0"
NAME = "TvOverlay"
SERICVE_NAME = NAME.lower()
MOCKED_TV_OVERLAY_INFO = {"result": {"settings": {"deviceName": NAME}}}

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_DEFAULT_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: DEFAULT_NAME,
}


def mocked_tvoverlay_info(device_name: str = NAME):
    """Create mocked tvoverlay info."""
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications.async_connect",
        return_value=MOCKED_TV_OVERLAY_INFO,
    )


def mocked_send_notification():
    """Create mocked tvoverlay send notification."""
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications.async_send",
        return_value=MOCKED_TV_OVERLAY_INFO,
    )


def mocked_send_persistent_notification():
    """Create mocked tvoverlay persistent notification."""
    return patch(
        "homeassistant.components.tvoverlay.config_flow.Notifications.async_send_fixed",
        return_value=MOCKED_TV_OVERLAY_INFO,
    )
