"""Test the jellyfin config flow."""
from unittest.mock import patch

from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

URL = "https://example.com"
USERNAME = "test-username"
PASSWORD = "test-password"

MOCK_SUCCESFUL_CONNECTION_STATE = {"State": CONNECTION_STATE["ServerSignIn"]}
MOCK_SUCCESFUL_LOGIN_RESPONSE = {"AccessToken": "Test"}
MOCK_USER_SETTINGS = {"Id": "123"}


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
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jellyfin.config_flow.ConnectionManager.connect_to_address",
        return_value=MOCK_SUCCESFUL_CONNECTION_STATE,
    ) as mock_connect, patch(
        "homeassistant.components.jellyfin.config_flow.ConnectionManager.login",
        return_value=MOCK_SUCCESFUL_LOGIN_RESPONSE,
    ) as mock_login, patch(
        "homeassistant.components.jellyfin.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.jellyfin.config_flow.API.get_user_settings",
        return_value=MOCK_USER_SETTINGS,
    ) as mock_set_id:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: URL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == URL
    assert result2["data"] == {
        CONF_URL: URL,
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }

    assert len(mock_connect.mock_calls) == 1
    assert len(mock_login.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_set_id.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant):
    """Test we handle an unreachable server."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: URL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant):
    """Test that we can handle invalid credentials."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jellyfin.config_flow.ConnectionManager.connect_to_address",
        return_value=MOCK_SUCCESFUL_CONNECTION_STATE,
    ) as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: URL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}

    assert len(mock_connect.mock_calls) == 1


async def test_form_exception(hass: HomeAssistant):
    """Test we handle an unexpected exception during server setup."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.jellyfin.config_flow.ConnectionManager.connect_to_address",
        side_effect=Exception("UnknownException"),
    ) as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: URL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}

    assert len(mock_connect.mock_calls) == 1
