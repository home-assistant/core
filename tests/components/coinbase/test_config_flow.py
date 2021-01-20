"""Test the Coinbase config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.coinbase.config_flow import InvalidAuth
from homeassistant.components.coinbase.const import (
    CONF_CURRENCIES,
    CONF_EXCAHNGE_RATES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value={"name": "Test User"},
    ), patch(
        "coinbase.wallet.client.Client.get_accounts",
        return_value={
            "data": [
                {
                    "currency": "BTC",
                },
                {
                    "currency": "USD",
                },
            ]
        },
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value={"currency": "USD", "rates": {"ATOM": "0.109", "BTC": "0.00002"}},
    ), patch(
        "homeassistant.components.coinbase.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.coinbase.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
                CONF_CURRENCIES: "BTC, USD",
                CONF_EXCAHNGE_RATES: "ATOM, BTC",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test User"
    assert result2["data"] == {
        CONF_API_KEY: "123456",
        CONF_API_TOKEN: "AbCDeF",
        CONF_CURRENCIES: ["BTC", "USD"],
        CONF_EXCAHNGE_RATES: ["ATOM", "BTC"],
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
                CONF_CURRENCIES: "BTC, USD",
                CONF_EXCAHNGE_RATES: "ATOM, BTC",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
                CONF_CURRENCIES: "BTC, USD",
                CONF_EXCAHNGE_RATES: "ATOM, BTC",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_bad_account_currency(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value={"name": "Test User"},
    ), patch(
        "coinbase.wallet.client.Client.get_accounts",
        return_value={
            "data": [
                {
                    "currency": "BTC",
                },
                {
                    "currency": "USD",
                },
            ]
        },
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value={"currency": "USD", "rates": {"ATOM": "0.109", "BTC": "0.00002"}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
                CONF_CURRENCIES: "NOT_A_CURRENCY",
                CONF_EXCAHNGE_RATES: "ATOM, BTC",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "currency_unavaliable"}


async def test_form_bad_exchange_rate(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value={"name": "Test User"},
    ), patch(
        "coinbase.wallet.client.Client.get_accounts",
        return_value={
            "data": [
                {
                    "currency": "BTC",
                },
                {
                    "currency": "USD",
                },
            ]
        },
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value={"currency": "USD", "rates": {"ATOM": "0.109", "BTC": "0.00002"}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
                CONF_CURRENCIES: "BTC, USD",
                CONF_EXCAHNGE_RATES: "NOT_A_RATE",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "exchange_rate_unavaliable"}
