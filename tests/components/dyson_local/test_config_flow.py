"""Tests for Dyson Local config flow."""
from unittest.mock import MagicMock, patch

from libdyson import DysonDevice
from libdyson.const import DEVICE_TYPE_360_EYE, DEVICE_TYPE_NAMES
from libdyson.exceptions import (
    DysonConnectTimeout,
    DysonFailedToParseWifiInfo,
    DysonInvalidCredential,
)

from homeassistant.components.dyson_local.config_flow import CONF_SSID
from homeassistant.components.dyson_local.const import (
    CONF_CREDENTIAL,
    CONF_DEVICE_TYPE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import CREDENTIAL, HOST, MODULE, SERIAL


def _get_mocked_device(error=None):
    device = MagicMock(spec=DysonDevice)
    type(device).connect = MagicMock(side_effect=error)
    return device


async def _async_init_flow(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return result["flow_id"]


async def test_flow_user(hass: HomeAssistant):
    """Test user flow."""
    flow_id = await _async_init_flow(hass)
    user_input = {CONF_SSID: "ssid", CONF_PASSWORD: "password", CONF_HOST: HOST}

    # parse failed
    with patch(
        f"{MODULE}.config_flow.get_mqtt_info_from_wifi_info",
        side_effect=DysonFailedToParseWifiInfo,
    ) as mock_parse:
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_parse_wifi_info"}
    mock_parse.assert_called_once_with("ssid", "password")

    patch(
        f"{MODULE}.config_flow.get_mqtt_info_from_wifi_info",
        return_value=(SERIAL, CREDENTIAL, DEVICE_TYPE_360_EYE),
    ).start()

    # cannot connect
    device = _get_mocked_device(DysonConnectTimeout)
    with patch(
        f"{MODULE}.config_flow.get_device", return_value=device
    ) as mock_get_device:
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["errors"] == {"base": "cannot_connect"}
    mock_get_device.assert_called_once_with(SERIAL, CREDENTIAL, DEVICE_TYPE_360_EYE)
    device.connect.assert_called_once_with(HOST)

    # invalid auth
    device = _get_mocked_device(DysonInvalidCredential)
    with patch(f"{MODULE}.config_flow.get_device", return_value=device):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["errors"] == {"base": "invalid_auth"}

    # success
    device = _get_mocked_device()
    with patch(f"{MODULE}.config_flow.get_device", return_value=device,), patch(
        f"{MODULE}.async_setup",
        return_value=True,
    ), patch(
        f"{MODULE}.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEVICE_TYPE_NAMES[DEVICE_TYPE_360_EYE]
    assert result["data"] == {
        CONF_SERIAL: SERIAL,
        CONF_CREDENTIAL: CREDENTIAL,
        CONF_DEVICE_TYPE: DEVICE_TYPE_360_EYE,
        CONF_NAME: DEVICE_TYPE_NAMES[DEVICE_TYPE_360_EYE],
        CONF_HOST: HOST,
    }

    # already configured
    flow_id = await _async_init_flow(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
