"""Define tests for the Tile config flow."""
from unittest.mock import patch

from pytile.errors import TileError

from homeassistant import data_entry_flow
from homeassistant.components.tile import DOMAIN
from homeassistant.components.tile.const import CONF_SHOW_INACTIVE
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONF = {
    CONF_USERNAME: "user@host.com",
    CONF_PASSWORD: "123abc",
}


async def test_duplicate_error(hass: HomeAssistant):
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=CONF).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_credentials(hass: HomeAssistant):
    """Test that invalid credentials key throws an error."""
    with patch(
        "homeassistant.components.tile.config_flow.async_login",
        side_effect=TileError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_step_import(hass: HomeAssistant):
    """Test that the import step works."""
    with patch(
        "homeassistant.components.tile.async_setup_entry", return_value=True
    ), patch("homeassistant.components.tile.config_flow.async_login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@host.com"
        assert result["data"] == CONF


async def test_step_user(hass: HomeAssistant):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.tile.async_setup_entry", return_value=True
    ), patch("homeassistant.components.tile.config_flow.async_login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@host.com"
        assert result["data"] == {
            CONF_USERNAME: "user@host.com",
            CONF_PASSWORD: "123abc",
        }


async def test_options_flow(hass: HomeAssistant):
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=CONF)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result.get("type") == data_entry_flow.RESULT_TYPE_FORM
    assert result.get("step_id") == "init"
    assert "flow_id" in result

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SHOW_INACTIVE: True},
    )

    assert result.get("type") == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result.get("data") == {CONF_SHOW_INACTIVE: True}
