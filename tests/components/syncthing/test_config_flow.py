"""Tests for syncthing config flow."""

from aiosyncthing.exceptions import UnauthorizedError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.syncthing.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL

from tests.async_mock import patch
from tests.common import MockConfigEntry

NAME = "Syncthing"
URL = "http://127.0.0.1:8384"
TOKEN = "token"
VERIFY_SSL = True

MOCK_ENTRY = {
    CONF_NAME: NAME,
    CONF_URL: URL,
    CONF_TOKEN: TOKEN,
    CONF_VERIFY_SSL: VERIFY_SSL,
}


@pytest.fixture
def mock_listening():
    """Mock listening."""
    with patch("homeassistant.components.syncthing.SyncthingClient.subscribe"):
        yield


async def test_show_setup_form(hass):
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_flow_successfull(hass, mock_listening):
    """Test with required fields only."""
    with patch("aiosyncthing.system.System.config"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={
                CONF_NAME: NAME,
                CONF_URL: URL,
                CONF_TOKEN: TOKEN,
                CONF_VERIFY_SSL: VERIFY_SSL,
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Syncthing (http://127.0.0.1:8384)"
        assert result["data"][CONF_NAME] == NAME
        assert result["data"][CONF_URL] == URL
        assert result["data"][CONF_TOKEN] == TOKEN
        assert result["data"][CONF_VERIFY_SSL] == VERIFY_SSL


async def test_flow_already_configured(hass):
    """Test name is already configured."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_ENTRY,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"]["name"] == "already_configured"


async def test_flow_invalid_auth(hass):
    """Test invalid auth."""

    with patch("aiosyncthing.system.System.config", side_effect=UnauthorizedError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_ENTRY,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"]["token"] == "invalid_auth"


async def test_flow_cannot_connect(hass):
    """Test cannot connect."""

    with patch("aiosyncthing.system.System.config", side_effect=Exception):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_ENTRY,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"]["base"] == "cannot_connect"
