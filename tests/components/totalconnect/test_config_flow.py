"""Tests for the iCloud config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.totalconnect.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER

from tests.common import MockConfigEntry, mock_coro

USERNAME = "username@me.com"
USERNAME_2 = "second_username@icloud.com"
PASSWORD = "password"


async def test_user(hass):
    """Test user config."""
    # no data provided so show the form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # now data is provided, so check if login is correct and create the entry
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock:
        client_mock.return_value.is_valid_credentials.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_import(hass):
    """Test import step with good username and password."""
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectConfigFlow.is_valid",
        return_value=mock_coro(True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_abort_if_already_setup(hass):
    """Test abort if the account is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        unique_id=USERNAME,
    ).add_to_hass(hass)

    # Should fail, same USERNAME (import)
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectConfigFlow.is_valid",
        return_value=mock_coro(True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same USERNAME (flow)
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectConfigFlow.is_valid",
        return_value=mock_coro(True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_login_failed(hass):
    """Test when we have errors during login."""
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectConfigFlow.is_valid",
        return_value=mock_coro(False),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "login"}
