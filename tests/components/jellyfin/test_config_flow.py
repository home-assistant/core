"""Test the jellyfin config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    MOCK_SUCCESFUL_CONNECTION_STATE,
    MOCK_SUCCESFUL_LOGIN_RESPONSE,
    MOCK_UNSUCCESFUL_CONNECTION_STATE,
    MOCK_UNSUCCESFUL_LOGIN_RESPONSE,
    MOCK_USER_SETTINGS,
    TEST_PASSWORD,
    TEST_URL,
    TEST_USERNAME,
)

from tests.common import MockConfigEntry


async def test_abort_if_existing_entry(hass: HomeAssistant):
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_form(hass: HomeAssistant):
    """Test the complete configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jellyfin.client_wrapper.ConnectionManager.connect_to_address",
        return_value=MOCK_SUCCESFUL_CONNECTION_STATE,
    ) as mock_connect, patch(
        "homeassistant.components.jellyfin.client_wrapper.ConnectionManager.login",
        return_value=MOCK_SUCCESFUL_LOGIN_RESPONSE,
    ) as mock_login, patch(
        "homeassistant.components.jellyfin.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.jellyfin.client_wrapper.API.get_user_settings",
        return_value=MOCK_USER_SETTINGS,
    ) as mock_set_id:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_URL
    assert result2["data"] == {
        CONF_URL: TEST_URL,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }

    assert len(mock_connect.mock_calls) == 1
    assert len(mock_login.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_set_id.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant):
    """Test we handle an unreachable server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jellyfin.client_wrapper.ConnectionManager.connect_to_address",
        return_value=MOCK_UNSUCCESFUL_CONNECTION_STATE,
    ) as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

    assert len(mock_connect.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant):
    """Test that we can handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jellyfin.client_wrapper.ConnectionManager.connect_to_address",
        return_value=MOCK_SUCCESFUL_CONNECTION_STATE,
    ) as mock_connect, patch(
        "homeassistant.components.jellyfin.client_wrapper.ConnectionManager.login",
        return_value=MOCK_UNSUCCESFUL_LOGIN_RESPONSE,
    ) as mock_login:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}

    assert len(mock_connect.mock_calls) == 1
    assert len(mock_login.mock_calls) == 1


async def test_form_exception(hass: HomeAssistant):
    """Test we handle an unexpected exception during server setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jellyfin.client_wrapper.ConnectionManager.connect_to_address",
        side_effect=Exception("UnknownException"),
    ) as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}

    assert len(mock_connect.mock_calls) == 1
