"""Test the Coinbase config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.coinbase.const import (
    CONF_CURRENCIES,
    CONF_EXCHANGE_PRECISION,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_API_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    init_mock_coinbase_v3,
    mock_get_exchange_rates,
    mock_get_portfolios,
    mocked_get_accounts_v3,
)

from tests.components.coinbase.const import GOOD_CURRENCY, GOOD_EXCHANGE_RATE


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch("coinbase.rest.RESTClient.get_accounts", new=mocked_get_accounts_v3),
        patch(
            "coinbase.rest.RESTClient.get_portfolios",
            return_value=mock_get_portfolios(),
        ),
        patch(
            "coinbase.rest.RESTBase.get",
            return_value={"data": mock_get_exchange_rates()},
        ),
        patch(
            "homeassistant.components.coinbase.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "organizations/123456", CONF_API_TOKEN: "AbCDeF"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Default"
    assert result2["data"] == {
        CONF_API_KEY: "organizations/123456",
        CONF_API_TOKEN: "AbCDeF",
        CONF_API_VERSION: "v3",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_option_form(hass: HomeAssistant) -> None:
    """Test we handle a good wallet currency option."""

    with (
        patch("coinbase.rest.RESTClient.get_accounts", new=mocked_get_accounts_v3),
        patch(
            "coinbase.rest.RESTClient.get_portfolios",
            return_value=mock_get_portfolios(),
        ),
        patch(
            "coinbase.rest.RESTBase.get",
            return_value={"data": mock_get_exchange_rates()},
        ),
        patch(
            "homeassistant.components.coinbase.update_listener"
        ) as mock_update_listener,
    ):
        config_entry = await init_mock_coinbase_v3(hass)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CURRENCIES: [GOOD_CURRENCY],
                CONF_EXCHANGE_RATES: [GOOD_EXCHANGE_RATE],
                CONF_EXCHANGE_PRECISION: 5,
            },
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert len(mock_update_listener.mock_calls) == 1
