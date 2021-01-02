"""Tests for the iCloud config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.totalconnect.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER

from .common import CONFIG_DATA, CONFIG_DATA_NO_USERCODES, USERNAME

from tests.common import MockConfigEntry


async def test_user(hass):
    """Test user step."""
    # user starts with no data entered, so show the user form
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=None,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_user_show_locations(hass):
    """Test user locations form."""
    # user/pass provided, so check if valid then ask for usercodes on locations form
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock:
        client_mock.return_value.is_valid_credentials.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA_NO_USERCODES,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "locations"


async def test_user_all_info(hass):
    """Test all user info included."""
    # user/pass/usercodes provided, so check if correct and create the entry
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock, patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectLocation"
    ) as location_mock:
        client_mock.return_value.is_valid_credentials.return_value = True
        location_mock.return_value.set_usercode.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_abort_if_already_setup(hass):
    """Test abort if the account is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=USERNAME,
    ).add_to_hass(hass)

    # Should fail, same USERNAME (flow)
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock:
        client_mock.return_value.is_valid_credentials.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_login_failed(hass):
    """Test when we have errors during login."""
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient.TotalConnectClient"
    ) as client_mock:
        client_mock.return_value.is_valid_credentials.return_value = False
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}
