"""Test the Wolf SmartSet Service config flow."""
from unittest.mock import patch

from httpcore import ConnectError
from wolf_smartset.models import Device
from wolf_smartset.token_auth import InvalidAuth

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.wolflink.const import (
    DEVICE_GATEWAY,
    DEVICE_ID,
    DEVICE_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

CONFIG = {
    DEVICE_NAME: "test-device",
    DEVICE_ID: 1234,
    DEVICE_GATEWAY: 5678,
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}

INPUT_CONFIG = {
    CONF_USERNAME: CONFIG[CONF_USERNAME],
    CONF_PASSWORD: CONFIG[CONF_PASSWORD],
}

DEVICE = Device(CONFIG[DEVICE_ID], CONFIG[DEVICE_GATEWAY], CONFIG[DEVICE_NAME])


async def test_show_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_device_step_form(hass):
    """Test we get the second step of config."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "device"


async def test_create_entry(hass):
    """Test entity creation from device step."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE],
    ), patch("homeassistant.components.wolflink.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

        result_create_entry = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_name": CONFIG[DEVICE_NAME]},
        )

    assert result_create_entry["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result_create_entry["title"] == CONFIG[DEVICE_NAME]
    assert result_create_entry["data"] == CONFIG


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=ConnectError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass):
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured_error(hass):
    """Test already configured while creating entry."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE],
    ), patch("homeassistant.components.wolflink.async_setup_entry", return_value=True):

        MockConfigEntry(
            domain=DOMAIN, unique_id=CONFIG[DEVICE_ID], data=CONFIG
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

        result_create_entry = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device_name": CONFIG[DEVICE_NAME]},
        )

    assert result_create_entry["type"] == data_entry_flow.FlowResultType.ABORT
    assert result_create_entry["reason"] == "already_configured"
