"""Config flow for Coinbase integration."""

from __future__ import annotations

import logging
from typing import Any

from coinbase.rest import RESTClient
from coinbase.rest.rest_base import HTTPError
from coinbase.wallet.client import Client as LegacyClient
from coinbase.wallet.error import AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_API_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from . import CoinbaseConfigEntry, get_accounts
from .const import (
    ACCOUNT_IS_VAULT,
    API_ACCOUNT_CURRENCY,
    API_DATA,
    API_RATES,
    CONF_CURRENCIES,
    CONF_EXCHANGE_BASE,
    CONF_EXCHANGE_PRECISION,
    CONF_EXCHANGE_PRECISION_DEFAULT,
    CONF_EXCHANGE_RATES,
    DOMAIN,
    RATES,
    WALLETS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)


def get_user_from_client(api_key, api_token):
    """Get the user name from Coinbase API credentials."""
    if "organizations" not in api_key:
        client = LegacyClient(api_key, api_token)
        return client.get_current_user()["name"]
    client = RESTClient(api_key=api_key, api_secret=api_token)
    return client.get_portfolios()["portfolios"][0]["name"]


async def validate_api(hass: HomeAssistant, data):
    """Validate the credentials."""

    try:
        user = await hass.async_add_executor_job(
            get_user_from_client, data[CONF_API_KEY], data[CONF_API_TOKEN]
        )
    except (AuthenticationError, HTTPError) as error:
        if "api key" in str(error) or " 401 Client Error" in str(error):
            _LOGGER.debug("Coinbase rejected API credentials due to an invalid API key")
            raise InvalidKey from error
        if "invalid signature" in str(
            error
        ) or "'Could not deserialize key data" in str(error):
            _LOGGER.debug(
                "Coinbase rejected API credentials due to an invalid API secret"
            )
            raise InvalidSecret from error
        _LOGGER.debug("Coinbase rejected API credentials due to an unknown error")
        raise InvalidAuth from error
    except ConnectionError as error:
        raise CannotConnect from error
    api_version = "v3" if "organizations" in data[CONF_API_KEY] else "v2"
    return {"title": user, "api_version": api_version}


async def validate_options(
    hass: HomeAssistant, config_entry: CoinbaseConfigEntry, options
):
    """Validate the requested resources are provided by API."""

    client = config_entry.runtime_data.client

    accounts = await hass.async_add_executor_job(
        get_accounts, client, config_entry.data.get("api_version", "v2")
    )

    accounts_currencies = [
        account[API_ACCOUNT_CURRENCY]
        for account in accounts
        if not account[ACCOUNT_IS_VAULT]
    ]
    if config_entry.data.get("api_version", "v2") == "v2":
        available_rates = await hass.async_add_executor_job(client.get_exchange_rates)
    else:
        resp = await hass.async_add_executor_job(client.get, "/v2/exchange-rates")
        available_rates = resp[API_DATA]
    if CONF_CURRENCIES in options:
        for currency in options[CONF_CURRENCIES]:
            if currency not in accounts_currencies:
                raise CurrencyUnavailable

    if CONF_EXCHANGE_RATES in options:
        for rate in options[CONF_EXCHANGE_RATES]:
            if rate not in available_rates[API_RATES]:
                raise ExchangeRateUnavailable

    return True


class CoinbaseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coinbase."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})

        try:
            info = await validate_api(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidKey:
            errors["base"] = "invalid_auth_key"
        except InvalidSecret:
            errors["base"] = "invalid_auth_secret"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            user_input[CONF_API_VERSION] = info["api_version"]
            return self.async_create_entry(title=info["title"], data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: CoinbaseConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle a option flow for Coinbase."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        errors = {}
        default_currencies = self.config_entry.options.get(CONF_CURRENCIES, [])
        default_exchange_rates = self.config_entry.options.get(CONF_EXCHANGE_RATES, [])
        default_exchange_base = self.config_entry.options.get(CONF_EXCHANGE_BASE, "USD")
        default_exchange_precision = self.config_entry.options.get(
            CONF_EXCHANGE_PRECISION, CONF_EXCHANGE_PRECISION_DEFAULT
        )

        if user_input is not None:
            # Pass back user selected options, even if bad
            if CONF_CURRENCIES in user_input:
                default_currencies = user_input[CONF_CURRENCIES]

            if CONF_EXCHANGE_RATES in user_input:
                default_exchange_rates = user_input[CONF_EXCHANGE_RATES]

            if CONF_EXCHANGE_RATES in user_input:
                default_exchange_base = user_input[CONF_EXCHANGE_BASE]

            if CONF_EXCHANGE_PRECISION in user_input:
                default_exchange_precision = user_input[CONF_EXCHANGE_PRECISION]

            try:
                await validate_options(self.hass, self.config_entry, user_input)
            except CurrencyUnavailable:
                errors["base"] = "currency_unavailable"
            except ExchangeRateUnavailable:
                errors["base"] = "exchange_rate_unavailable"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CURRENCIES,
                        default=default_currencies,
                    ): cv.multi_select(WALLETS),
                    vol.Optional(
                        CONF_EXCHANGE_RATES,
                        default=default_exchange_rates,
                    ): cv.multi_select(RATES),
                    vol.Optional(
                        CONF_EXCHANGE_BASE,
                        default=default_exchange_base,
                    ): vol.In(WALLETS),
                    vol.Optional(
                        CONF_EXCHANGE_PRECISION, default=default_exchange_precision
                    ): int,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidSecret(HomeAssistantError):
    """Error to indicate auth failed due to invalid secret."""


class InvalidKey(HomeAssistantError):
    """Error to indicate auth failed due to invalid key."""


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate Coinbase API Key is already configured."""


class CurrencyUnavailable(HomeAssistantError):
    """Error to indicate the requested currency resource is not provided by the API."""


class ExchangeRateUnavailable(HomeAssistantError):
    """Error to indicate the requested exchange rate resource is not provided by the API."""
