"""Define tests for the Tile config flow."""
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant import data_entry_flow
from homeassistant.components.dremel_3d_printer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_duplicate_error(hass, config, api):
    """Test that errors are shown when adding a duplicate config."""

    with patch(
        "homeassistant.components.dremel_3d_printer.config_flow.Dremel3DPrinter",
        return_value=api,
    ), patch(
        "homeassistant.components.dremel_3d_printer.async_setup_entry",
        return_value=True,
    ):
        MockConfigEntry(
            domain=DOMAIN, unique_id=api.get_serial_number(), data=config
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "err,err_string",
    [
        (ConnectTimeout, "cannot_connect"),
        (HTTPError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_errors(hass, config, err, err_string):
    """Test that errors are handled correctly."""
    with patch(
        "homeassistant.components.dremel_3d_printer.config_flow.Dremel3DPrinter",
        side_effect=err,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": err_string}


async def test_step_user(hass, config, api):
    """Test that the user step works."""

    with patch(
        "homeassistant.components.dremel_3d_printer.config_flow.Dremel3DPrinter",
        return_value=api,
    ), patch(
        "homeassistant.components.dremel_3d_printer.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "FooTitle"
        assert result["data"][CONF_HOST] == "1.1.1.1"
        assert len(list(result["data"])) == 1
        assert result["result"].unique_id == "FooSN"
