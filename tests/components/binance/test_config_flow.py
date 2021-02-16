"""Define tests for the Binance config flow."""
import json
from unittest.mock import patch

from aiobinanceapi.errors import (
    BinanceApiError,
    BinanceInvalidAuthentication,
    BinanceResponseError,
)

from homeassistant import data_entry_flow, setup
from homeassistant.components.binance.const import (
    CONF_API_SECRET,
    CONF_BALANCES,
    CONF_MARKETS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE

from . import (
    INTEGRATION_TITLE,
    INTEGRATION_TITLE_MARKETS_ONLY,
    USER_INPUT,
    USER_INPUT_BALANCES,
    USER_INPUT_MARKETS,
)

from tests.common import MockConfigEntry, load_fixture


async def test_show_form(hass):
    """Test that the form is served with no input."""
    await setup.async_setup_component(hass, "persistent_notification", {})

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
        "homeassistant.components.binance.Binance.get_markets",
        return_value=json.loads(load_fixture("binance/markets_data.json")),
    ), patch(
        "homeassistant.components.binance.Binance.get_account",
        return_value=json.loads(load_fixture("binance/account_data.json")),
    ), patch(
        "homeassistant.components.binance.Binance.get_balances",
        return_value=json.loads(load_fixture("binance/balances_data.json")),
    ), patch(
        "homeassistant.components.binance.async_setup_entry", return_value=True
    ):
        await setup.async_setup_component(hass, "persistent_notification", {})

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

        # Balances form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "balances"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT_BALANCES
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == INTEGRATION_TITLE

        assert result["data"]
        assert result["data"][CONF_API_KEY] == USER_INPUT[CONF_API_KEY]
        assert result["data"][CONF_API_SECRET] == USER_INPUT[CONF_API_SECRET]
        assert result["data"][CONF_MARKETS] == USER_INPUT_MARKETS[CONF_MARKETS]
        assert result["data"][CONF_BALANCES] == USER_INPUT_BALANCES[CONF_BALANCES]

        assert result["result"]


async def test_user_form_without_balances(hass):
    """Test we get the user initiated form."""
    with patch(
        "homeassistant.components.binance.Binance.get_markets",
        return_value=json.loads(load_fixture("binance/markets_data.json")),
    ), patch(
        "homeassistant.components.binance.Binance.get_account",
        return_value=json.loads(load_fixture("binance/account_data.json")),
    ), patch(
        "homeassistant.components.binance.Binance.get_balances",
        return_value={},
    ), patch(
        "homeassistant.components.binance.async_setup_entry", return_value=True
    ):
        await setup.async_setup_component(hass, "persistent_notification", {})

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

        # Balances form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "balances"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == INTEGRATION_TITLE_MARKETS_ONLY

        assert result["data"]
        assert result["data"][CONF_API_KEY] == USER_INPUT[CONF_API_KEY]
        assert result["data"][CONF_API_SECRET] == USER_INPUT[CONF_API_SECRET]
        assert result["data"][CONF_MARKETS] == USER_INPUT_MARKETS[CONF_MARKETS]

        assert result["result"]


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.binance.Binance.get_markets",
        return_value=json.loads(load_fixture("binance/markets_data.json")),
    ), patch("homeassistant.components.binance.async_setup_entry", return_value=True):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER


async def test_invalid_api_key(hass):
    """Test that errors are shown when API key is invalid."""
    with patch(
        "homeassistant.components.binance.Binance.get_markets",
        side_effect=BinanceInvalidAuthentication("Invalid API key"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["errors"] == {"base": "invalid_auth"}


async def test_invalid_api_response(hass):
    """Test that errors are shown when API request is invalid."""
    with patch(
        "homeassistant.components.binance.Binance.get_markets",
        side_effect=BinanceResponseError("Failed", "Invalid API Response"),
    ), patch(
        "homeassistant.components.binance.Binance.get_account",
        return_value=json.loads(load_fixture("binance/account_data.json")),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["errors"] == {"base": "invalid_response"}


async def test_api_error(hass):
    """Test that errors are shown when the API returns an error."""
    with patch(
        "homeassistant.components.binance.Binance.get_markets",
        side_effect=BinanceApiError("Invalid API Response"),
    ), patch(
        "homeassistant.components.binance.Binance.get_account",
        return_value=json.loads(load_fixture("binance/account_data.json")),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=USER_INPUT,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_api_unexpected_exception(hass):
    """Test that errors are shown when the API returns an unexpected exception."""
    with patch(
        "homeassistant.components.binance.Binance.get_markets",
        side_effect=Exception("Unexpected exception"),
    ), patch(
        "homeassistant.components.binance.Binance.get_account",
        return_value=json.loads(load_fixture("binance/account_data.json")),
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
        "homeassistant.components.binance.Binance.get_markets",
        return_value=json.loads(load_fixture("binance/markets_data.json")),
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
