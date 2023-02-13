"""Test the Coinbase config flow."""
import logging
from unittest.mock import patch

from coinbase.wallet.error import AuthenticationError
import pytest
from requests.models import Response

from homeassistant import config_entries
from homeassistant.components.coinbase.const import (
    CONF_CURRENCIES,
    CONF_EXCHANGE_PRECISION,
    CONF_EXCHANGE_RATES,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .common import (
    init_mock_coinbase,
    mock_get_current_user,
    mock_get_exchange_rates,
    mocked_get_accounts,
)
from .const import BAD_CURRENCY, BAD_EXCHANGE_RATE, GOOD_CURRENCY, GOOD_EXCHANGE_RATE


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ), patch(
        "homeassistant.components.coinbase.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test User"
    assert result2["data"] == {CONF_API_KEY: "123456", CONF_API_TOKEN: "AbCDeF"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    caplog.set_level(logging.DEBUG)

    response = Response()
    response.status_code = 401
    api_auth_error_unknown = AuthenticationError(
        response,
        "authentication_error",
        "unknown error",
        [{"id": "authentication_error", "message": "unknown error"}],
    )
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        side_effect=api_auth_error_unknown,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
    assert "Coinbase rejected API credentials due to an unknown error" in caplog.text

    api_auth_error_key = AuthenticationError(
        response,
        "authentication_error",
        "invalid api key",
        [{"id": "authentication_error", "message": "invalid api key"}],
    )
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        side_effect=api_auth_error_key,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth_key"}
    assert "Coinbase rejected API credentials due to an invalid API key" in caplog.text

    api_auth_error_secret = AuthenticationError(
        response,
        "authentication_error",
        "invalid signature",
        [{"id": "authentication_error", "message": "invalid signature"}],
    )
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        side_effect=api_auth_error_secret,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth_secret"}
    assert (
        "Coinbase rejected API credentials due to an invalid API secret" in caplog.text
    )


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
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
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_catch_all_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "123456",
                CONF_API_TOKEN: "AbCDeF",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_option_form(hass: HomeAssistant) -> None:
    """Test we handle a good wallet currency option."""

    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ), patch(
        "homeassistant.components.coinbase.update_listener"
    ) as mock_update_listener:
        config_entry = await init_mock_coinbase(hass)
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
        assert result2["type"] == "create_entry"
        await hass.async_block_till_done()
        assert len(mock_update_listener.mock_calls) == 1


async def test_form_bad_account_currency(hass: HomeAssistant) -> None:
    """Test we handle a bad currency option."""
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        config_entry = await init_mock_coinbase(hass)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CURRENCIES: [BAD_CURRENCY],
                CONF_EXCHANGE_RATES: [],
                CONF_EXCHANGE_PRECISION: 5,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "currency_unavailable"}


async def test_form_bad_exchange_rate(hass: HomeAssistant) -> None:
    """Test we handle a bad exchange rate."""
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        config_entry = await init_mock_coinbase(hass)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CURRENCIES: [],
                CONF_EXCHANGE_RATES: [BAD_EXCHANGE_RATE],
                CONF_EXCHANGE_PRECISION: 5,
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "exchange_rate_unavailable"}


async def test_option_catch_all_exception(hass: HomeAssistant) -> None:
    """Test we handle an unknown exception in the option flow."""
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ):
        config_entry = await init_mock_coinbase(hass)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "coinbase.wallet.client.Client.get_accounts",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_CURRENCIES: [],
                CONF_EXCHANGE_RATES: ["ETH"],
                CONF_EXCHANGE_PRECISION: 5,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
