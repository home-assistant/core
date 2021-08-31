"""Test the Bitvavo config flow."""
import json
from unittest.mock import patch

from bitvavo.BitvavoExceptions import BitvavoException

from homeassistant import data_entry_flow
from homeassistant.components.bitvavo.const import (
    CONF_API_SECRET,
    CONF_MARKETS,
    CONF_SHOW_EMPTY_ASSETS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE

from . import INTEGRATION_TITLE, USER_INPUT, USER_INPUT_MARKETS

from tests.common import MockConfigEntry, load_fixture


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()


async def test_user_form(hass):
    """Test we get the user initiated form."""
    with patch(
        "homeassistant.components.bitvavo.BitvavoClient.get_price_ticker",
        return_value=json.loads(load_fixture("bitvavo/ticker_data.json")),
    ), patch(
        "homeassistant.components.bitvavo.BitvavoClient.get_balance",
        return_value=json.loads(load_fixture("bitvavo/balance_data.json")),
    ), patch(
        "homeassistant.components.bitvavo.async_setup_entry", return_value=True
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )

        # User form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

        # Markets form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "markets"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT_MARKETS
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == INTEGRATION_TITLE

        assert result["data"]
        assert result["data"][CONF_API_KEY] == USER_INPUT[CONF_API_KEY]
        assert result["data"][CONF_API_SECRET] == USER_INPUT[CONF_API_SECRET]
        assert result["data"][CONF_MARKETS] == USER_INPUT_MARKETS[CONF_MARKETS]

        assert result["result"]


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.bitvavo.BitvavoClient.get_price_ticker",
        return_value=json.loads(load_fixture("bitvavo/ticker_data.json")),
    ), patch(
        "homeassistant.components.bitvavo.BitvavoClient.get_balance",
        return_value=json.loads(load_fixture("bitvavo/balance_data.json")),
    ), patch(
        "homeassistant.components.bitvavo.async_setup_entry", return_value=True
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "markets"


async def test_invalid_auth_response(hass):
    """Test that errors are shown when API request is invalid."""
    with patch(
        "homeassistant.components.bitvavo.BitvavoClient.get_price_ticker",
        side_effect=BitvavoException("403", "Invalid Auth"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["errors"] == {"base": "invalid_auth"}


async def test_api_unexpected_exception(hass):
    """Test that errors are shown when the API returns an unexpected exception."""
    with patch(
        "homeassistant.components.bitvavo.BitvavoClient.get_price_ticker",
        side_effect=Exception("Unexpected exception"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["errors"] == {"base": "unknown"}


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""
    with patch(
        "homeassistant.components.bitvavo.BitvavoClient.get_price_ticker",
        return_value=json.loads(load_fixture("bitvavo/ticker_data.json")),
    ):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="123456",
            data=USER_INPUT,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "single_instance_allowed"


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data=USER_INPUT,
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.bitvavo.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_SHOW_EMPTY_ASSETS: True}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_SHOW_EMPTY_ASSETS: True}
