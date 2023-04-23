"""Test the flume config flow."""
from unittest.mock import MagicMock, patch

import requests.exceptions

from homeassistant import config_entries
from homeassistant.components.flume.const import DOMAIN
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _get_mocked_flume_device_list():
    flume_device_list_mock = MagicMock()
    type(flume_device_list_mock).device_list = ["mock"]
    return flume_device_list_mock


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form and can setup from user input."""

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


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
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
    assert result2["errors"] == {"password": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
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


async def test_reauth(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@test.org",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
        },
        unique_id="test@test.org",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "unique_id": "test@test.org"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

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
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"password": "invalid_auth"}

    with patch(
        "homeassistant.components.flume.config_flow.FlumeAuth",
        return_value=True,
    ), patch(
        "homeassistant.components.flume.config_flow.FlumeDeviceList",
        side_effect=requests.exceptions.ConnectionError(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "cannot_connect"}

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
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )

    assert mock_setup_entry.called
    assert result4["type"] == "abort"
    assert result4["reason"] == "reauth_successful"
