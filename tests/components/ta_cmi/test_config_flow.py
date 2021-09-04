"""Test the Technische Alternative C.M.I. config flow."""
from typing import Any, Dict
from unittest.mock import patch

from ta_cmi import ApiError, Device, InvalidCredentialsError, RateLimitError

from homeassistant import data_entry_flow
from homeassistant.components.ta_cmi.config_flow import ConfigFlow
from homeassistant.components.ta_cmi.const import (
    CONF_CHANNELS,
    CONF_CHANNELS_DEVICE_CLASS,
    CONF_CHANNELS_ID,
    CONF_CHANNELS_NAME,
    CONF_CHANNELS_TYPE,
    CONF_DEVICE_FETCH_MODE,
    CONF_DEVICES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

DUMMY_CONNECTION_DATA: Dict[str, Any] = {
    CONF_HOST: "http://1.2.3.4",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

DUMMY_DEVICE_DATA_NO_CHANNEL_FETCH_ALL = {
    CONF_DEVICES: [2],
    "edit_channels": False,
    CONF_DEVICE_FETCH_MODE: True,
}

DUMMY_DEVICE_DATA_NO_CHANNEL_FETCH_DEFINED = {
    CONF_DEVICES: [2],
    "edit_channels": False,
    CONF_DEVICE_FETCH_MODE: False,
}

DUMMY_DEVICE_DATA_EDIT_CHANNEL = {
    CONF_DEVICES: [2],
    "edit_channels": True,
    CONF_DEVICE_FETCH_MODE: False,
}

DUMMY_CHANNEL_DATA_NO_OTHER_EDIT = {
    "node": "2",
    CONF_CHANNELS_ID: 1,
    CONF_CHANNELS_TYPE: "Input",
    CONF_CHANNELS_NAME: "Name",
    CONF_CHANNELS_DEVICE_CLASS: "",
    "edit_more_channels": False,
}

DUMMY_CHANNEL_DATA_OTHER_EDIT = {
    "node": "2",
    CONF_CHANNELS_ID: 1,
    CONF_CHANNELS_TYPE: "Input",
    CONF_CHANNELS_NAME: "Name",
    CONF_CHANNELS_DEVICE_CLASS: "",
    "edit_more_channels": True,
}

DUMMY_DEVICE_API_DATA: Dict[str, Any] = {
    "Header": {"Version": 5, "Device": "87", "Timestamp": 1630764000},
    "Data": {
        "Inputs": [
            {"Number": 1, "AD": "A", "Value": {"Value": 92.2, "Unit": "1"}},
            {"Number": 2, "AD": "A", "Value": {"Value": 92.3, "Unit": "1"}},
        ],
        "Outputs": [{"Number": 1, "AD": "D", "Value": {"Value": 1, "Unit": "43"}}],
    },
    "Status": "OK",
    "Status code": 0,
}

DUMMY_DEVICE_API_DATA_UNKOWN_DEVICE: Dict[str, Any] = {
    "Header": {"Version": 5, "Device": "0", "Timestamp": 1630764000},
    "Data": {
        "Inputs": [
            {"Number": 1, "AD": "A", "Value": {"Value": 92.2, "Unit": "1"}},
            {"Number": 2, "AD": "A", "Value": {"Value": 92.3, "Unit": "1"}},
        ],
        "Outputs": [{"Number": 1, "AD": "D", "Value": {"Value": 1, "Unit": "43"}}],
    },
    "Status": "OK",
    "Status code": 0,
}


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection found."""
    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequestNoJson",
        side_effect=ApiError("Could not connect to C.M.I."),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_CONNECTION_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test starting a flow by user but with invalid credentials."""
    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequestNoJson",
        side_effect=InvalidCredentialsError("Invalid API key"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_CONNECTION_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}


async def test_step_user_unexpected_exception(hass: HomeAssistant) -> None:
    """Test starting a flow by user but with an unexpected exception."""
    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequestNoJson",
        side_effect=Exception("DUMMY"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_CONNECTION_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}


async def test_step_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequestNoJson",
        return_value="2;",
    ), patch("ta_cmi.baseApi.BaseAPI._makeRequest", return_value=DUMMY_DEVICE_API_DATA):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_CONNECTION_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "devices"
        assert result["errors"] == {}


async def test_step_user_unkown_device(hass: HomeAssistant) -> None:
    """Test to start a flow by a user with unknown device."""

    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequestNoJson",
        return_value="2;3;",
    ), patch(
        "ta_cmi.baseApi.BaseAPI._makeRequest",
        return_value=DUMMY_DEVICE_API_DATA_UNKOWN_DEVICE,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_CONNECTION_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "devices"
        assert result["errors"] == {}


async def test_step_devices_without_edit_fetch_all(hass: HomeAssistant) -> None:
    """Test the device step without edit channels and fetchmode all."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "devices"},
        data=DUMMY_DEVICE_DATA_NO_CHANNEL_FETCH_ALL,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "C.M.I"


async def test_step_devices_without_edit_fetch_defined(hass: HomeAssistant) -> None:
    """Test the device step without edit channels and fetchmode defined."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "devices"},
        data=DUMMY_DEVICE_DATA_NO_CHANNEL_FETCH_DEFINED,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "C.M.I"


async def test_step_devices_with_multiple_devices(hass: HomeAssistant) -> None:
    """Test the device step with multiple devices."""

    dummyDevice: Device = Device("2", "http://dummy", "", "")
    dummyDevice2: Device = Device("3", "http://dummy", "", "")

    DATA_OVERRIDE = {"allDevices": [dummyDevice, dummyDevice2]}

    with patch.object(ConfigFlow, "overrideData", DATA_OVERRIDE), patch(
        "ta_cmi.baseApi.BaseAPI._makeRequest",
        return_value=DUMMY_DEVICE_API_DATA_UNKOWN_DEVICE,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "devices"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "devices"
        assert result["errors"] == {}


async def test_step_devices_with_edit(hass: HomeAssistant) -> None:
    """Test the device step with edit channels."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "devices"},
        data=DUMMY_DEVICE_DATA_EDIT_CHANNEL,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "channel"
    assert result["errors"] == {}


async def test_step_device_unkown_error(hass: HomeAssistant) -> None:
    """Test the channel step with an unexpected error."""

    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequest",
        side_effect=ApiError("Could not connect to C.M.I"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "devices"},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "devices"
    assert result["errors"] == {"base": "unknown"}


async def test_step_device_rate_limit_error(hass: HomeAssistant) -> None:
    """Test the channel step with a rate limit error."""

    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequest",
        side_effect=RateLimitError("RateLimit"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "devices"},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "devices"
    assert result["errors"] == {"base": "rate_limit"}


async def test_step_channels_edit_only_one(hass: HomeAssistant) -> None:
    """Test the channel step without edit other channels."""

    dummyDevice: Device = Device("2", "", "", "")

    DATA_OVERRIDE = {"allDevices": [dummyDevice]}

    CONFIG_OVERRIDE = {
        CONF_DEVICES: [
            {CONF_CHANNELS_ID: "2", CONF_DEVICE_FETCH_MODE: "all", CONF_CHANNELS: []}
        ]
    }

    with patch.object(ConfigFlow, "overrideData", DATA_OVERRIDE), patch.object(
        ConfigFlow, "overrideConfig", CONFIG_OVERRIDE
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "channel"},
            data=DUMMY_CHANNEL_DATA_NO_OTHER_EDIT,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "C.M.I"


async def test_step_channels_edit_more(hass: HomeAssistant) -> None:
    """Test the channel step with edit other channels."""

    dummyDevice: Device = Device("2", "", "", "")

    DATA_OVERRIDE = {"allDevices": [dummyDevice], CONF_DEVICES: ["2"]}

    CONFIG_OVERRIDE = {
        CONF_DEVICES: [
            {CONF_CHANNELS_ID: "2", CONF_DEVICE_FETCH_MODE: "all", CONF_CHANNELS: []}
        ]
    }

    with patch.object(ConfigFlow, "overrideData", DATA_OVERRIDE), patch.object(
        ConfigFlow, "overrideConfig", CONFIG_OVERRIDE
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "channel"}, data=DUMMY_CHANNEL_DATA_OTHER_EDIT
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "channel"
        assert result["errors"] == {}
