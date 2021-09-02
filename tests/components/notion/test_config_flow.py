"""Define tests for the Notion config flow."""
from unittest.mock import patch

from aionotion.errors import InvalidCredentialsError, NotionError

from homeassistant import data_entry_flow
from homeassistant.components.notion import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_generic_notion_error(hass):
    """Test that a generic aionotion error is handled correctly."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    with patch(
        "homeassistant.components.notion.config_flow.async_get_client",
        side_effect=NotionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["errors"] == {"base": "unknown"}


async def test_invalid_credentials(hass):
    """Test that invalid credentials throw an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    with patch(
        "homeassistant.components.notion.config_flow.async_get_client",
        side_effect=InvalidCredentialsError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["errors"] == {"base": "invalid_auth"}


async def test_step_reauth(hass):
    """Test that the reauth step works."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@email.com",
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    with patch("homeassistant.components.notion.config_flow.async_get_client"), patch(
        "homeassistant.components.notion.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "password"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1


async def test_show_form(hass):
    """Test that the form is served with no input."""
    with patch("homeassistant.components.notion.config_flow.async_get_client"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    with patch(
        "homeassistant.components.notion.async_setup_entry", return_value=True
    ), patch("homeassistant.components.notion.config_flow.async_get_client"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@host.com"
        assert result["data"] == {
            CONF_USERNAME: "user@host.com",
            CONF_PASSWORD: "password123",
        }
