"""Tests for the TvOverlay integration."""
from unittest.mock import patch

from homeassistant.components.tvoverlay.const import DEFAULT_NAME
from homeassistant.const import CONF_HOST, CONF_NAME

HOST = "0.0.0.0"
NAME = "TvOverlay"

SERICVE_NAME = NAME.lower().replace(" ", "_")

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_DEFAULT_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: DEFAULT_NAME,
}


def mocked_tvoverlay_info(device_name: str = NAME):
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
