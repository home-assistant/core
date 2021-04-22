"""Test the flume config flow."""
from unittest.mock import MagicMock, patch

import requests.exceptions

from homeassistant import config_entries, setup
from homeassistant.components.flume.const import DOMAIN
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)


def _get_mocked_flume_device_list():
    flume_device_list_mock = MagicMock()
    type(flume_device_list_mock).device_list = ["mock"]
    return flume_device_list_mock


async def test_form(hass):
    """Test we get the form and can setup from user input."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_flume_device_list = _get_mocked_flume_device_list()

    with patch(
        "homeassistant.components.flume.config_flow.FlumeAuth",
        return_value=True,
    ), patch(
        "homeassistant.components.flume.config_flow.FlumeDeviceList",
        return_value=mock_flume_device_list,
    ), patch(
        "homeassistant.components.flume.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_CLIENT_ID: "client_id",
                CONF_CLIENT_SECRET: "client_secret",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_CLIENT_ID: "client_id",
        CONF_CLIENT_SECRET: "client_secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import(hass):
    """Test we can import the sensor platform config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_flume_device_list = _get_mocked_flume_device_list()

    with patch(
        "homeassistant.components.flume.config_flow.FlumeAuth",
        return_value=True,
    ), patch(
        "homeassistant.components.flume.config_flow.FlumeDeviceList",
        return_value=mock_flume_device_list,
    ), patch(
        "homeassistant.components.flume.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_CLIENT_ID: "client_id",
                CONF_CLIENT_SECRET: "client_secret",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_CLIENT_ID: "client_id",
        CONF_CLIENT_SECRET: "client_secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flume.config_flow.FlumeAuth",
        return_value=True,
    ), patch(
        "homeassistant.components.flume.config_flow.FlumeDeviceList",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_CLIENT_ID: "client_id",
                CONF_CLIENT_SECRET: "client_secret",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.flume.config_flow.FlumeAuth",
        return_value=True,
    ), patch(
        "homeassistant.components.flume.config_flow.FlumeDeviceList",
        side_effect=requests.exceptions.ConnectionError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_CLIENT_ID: "client_id",
                CONF_CLIENT_SECRET: "client_secret",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
