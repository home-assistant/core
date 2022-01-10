"""Define tests for the Tile config flow."""
from unittest.mock import patch

import pytest
from pytile.errors import InvalidAuthError, TileError

from homeassistant import data_entry_flow
from homeassistant.components.tile import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "123abc",
    }

    MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "err,err_string",
    [
        (InvalidAuthError, "invalid_auth"),
        (TileError, "unknown"),
    ],
)
async def test_errors(hass, err, err_string):
    """Test that errors are handled correctly."""
    conf = {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "123abc",
    }

    with patch(
        "homeassistant.components.tile.config_flow.async_login",
        side_effect=err,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": err_string}


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "123abc",
    }

    with patch(
        "homeassistant.components.tile.async_setup_entry", return_value=True
    ), patch("homeassistant.components.tile.config_flow.async_login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@host.com"
        assert result["data"] == {
            CONF_USERNAME: "user@host.com",
            CONF_PASSWORD: "123abc",
        }


async def test_step_reauth(hass):
    """Test that the reauth step works."""
    conf = {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "123abc",
    }

    MockConfigEntry(domain=DOMAIN, unique_id="user@host.com", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH},
        data={CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password"},
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.tile.async_setup_entry", return_value=True
    ), patch("homeassistant.components.tile.config_flow.async_login"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "password"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "123abc",
    }

    with patch(
        "homeassistant.components.tile.async_setup_entry", return_value=True
    ), patch("homeassistant.components.tile.config_flow.async_login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@host.com"
        assert result["data"] == {
            CONF_USERNAME: "user@host.com",
            CONF_PASSWORD: "123abc",
        }
