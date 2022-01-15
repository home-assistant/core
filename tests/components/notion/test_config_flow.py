"""Define tests for the Notion config flow."""
from unittest.mock import AsyncMock, patch

from aionotion.errors import InvalidCredentialsError, NotionError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.notion import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture(name="client")
def client_fixture():
    """Define a fixture for an aionotion client."""
    return AsyncMock(return_value=None)


@pytest.fixture(name="client_login")
def client_login_fixture(client):
    """Define a fixture for patching the aiowatttime coroutine to get a client."""
    with patch(
        "homeassistant.components.notion.config_flow.async_get_client"
    ) as mock_client:
        mock_client.side_effect = client
        yield mock_client


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("client", [AsyncMock(side_effect=NotionError)])
async def test_generic_notion_error(client_login, hass):
    """Test that a generic aionotion error is handled correctly."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["errors"] == {"base": "unknown"}


@pytest.mark.parametrize("client", [AsyncMock(side_effect=InvalidCredentialsError)])
async def test_invalid_credentials(client_login, hass):
    """Test that invalid credentials throw an error."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )
    await hass.async_block_till_done()

    assert result["errors"] == {"base": "invalid_auth"}


async def test_step_reauth(client_login, hass):
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

    with patch(
        "homeassistant.components.notion.async_setup_entry", return_value=True
    ), patch("homeassistant.config_entries.ConfigEntries.async_reload"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "password"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1


async def test_show_form(client_login, hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(client_login, hass):
    """Test that the user step works."""
    conf = {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"}

    with patch("homeassistant.components.notion.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "user@host.com"
    assert result["data"] == {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }
