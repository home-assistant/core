"""Tests for syncthing config flow."""
from unittest.mock import patch

from aiosyncthing.exceptions import UnauthorizedError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.syncthing.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

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


async def test_show_setup_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"


async def test_flow_successful(hass: HomeAssistant) -> None:
    """Test with required fields only."""
    with patch(
        "aiosyncthing.system.System.status", return_value={"myID": "server-id"}
    ), patch(
        "homeassistant.components.syncthing.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "http://127.0.0.1:8384"
        assert result["data"][CONF_NAME] == NAME
        assert result["data"][CONF_URL] == URL
        assert result["data"][CONF_TOKEN] == TOKEN
        assert result["data"][CONF_VERIFY_SSL] == VERIFY_SSL
        assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_already_configured(hass: HomeAssistant) -> None:
    """Test name is already configured."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY, unique_id="server-id")
    entry.add_to_hass(hass)

    with patch("aiosyncthing.system.System.status", return_value={"myID": "server-id"}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=MOCK_ENTRY,
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth."""

    with patch("aiosyncthing.system.System.status", side_effect=UnauthorizedError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=MOCK_ENTRY,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["token"] == "invalid_auth"


async def test_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test cannot connect."""

    with patch("aiosyncthing.system.System.status", side_effect=Exception):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=MOCK_ENTRY,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"
