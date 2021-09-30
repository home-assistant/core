"""Test the Coinbase config flow."""
from unittest.mock import patch

from coinbase.wallet.error import AuthenticationError
from requests.models import Response

from homeassistant import config_entries, setup
from homeassistant.components.coinbase.const import (
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    CONF_YAML_API_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN

from .common import (
    init_mock_coinbase,
    mock_get_current_user,
    mock_get_exchange_rates,
    mocked_get_accounts,
)
from .const import BAD_CURRENCY, BAD_EXCHANGE_RATE, GOOD_CURRENCY, GOOD_EXCHANGE_RATE

from tests.common import MockConfigEntry


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
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
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
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test User"
    assert result2["data"] == {CONF_API_KEY: "123456", CONF_API_TOKEN: "AbCDeF"}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    response = Response()
    response.status_code = 401
    api_auth_error = AuthenticationError(
        response,
        "authentication_error",
        "invalid signature",
        [{"id": "authentication_error", "message": "invalid signature"}],
    )
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        side_effect=api_auth_error,
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
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_catch_all_exception(hass):
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


async def test_option_form(hass):
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
            },
        )
        assert result2["type"] == "create_entry"
        await hass.async_block_till_done()
        assert len(mock_update_listener.mock_calls) == 1


async def test_form_bad_account_currency(hass):
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
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "currency_unavaliable"}


async def test_form_bad_exchange_rate(hass):
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
            },
        )
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "exchange_rate_unavaliable"}


async def test_option_catch_all_exception(hass):
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
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_yaml_import(hass):
    """Test YAML import works."""
    conf = {
        CONF_API_KEY: "123456",
        CONF_YAML_API_TOKEN: "AbCDeF",
        CONF_CURRENCIES: ["BTC", "USD"],
        CONF_EXCHANGE_RATES: ["ATOM", "BTC"],
    }
    with patch(
        "coinbase.wallet.client.Client.get_current_user",
        return_value=mock_get_current_user(),
    ), patch(
        "coinbase.wallet.client.Client.get_accounts", new=mocked_get_accounts
    ), patch(
        "coinbase.wallet.client.Client.get_exchange_rates",
        return_value=mock_get_exchange_rates(),
    ), patch(
        "homeassistant.components.coinbase.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.coinbase.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
        )
    assert result["type"] == "create_entry"
    assert result["title"] == "Test User"
    assert result["data"] == {CONF_API_KEY: "123456", CONF_API_TOKEN: "AbCDeF"}
    assert result["options"] == {
        CONF_CURRENCIES: ["BTC", "USD"],
        CONF_EXCHANGE_RATES: ["ATOM", "BTC"],
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_yaml_existing(hass):
    """Test YAML ignored when already processed."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "123456",
            CONF_API_TOKEN: "AbCDeF",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_API_KEY: "123456",
            CONF_YAML_API_TOKEN: "AbCDeF",
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
