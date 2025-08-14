"""Config flow for Coinbase integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from coinbase.rest import RESTClient
from coinbase.rest.rest_base import HTTPError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
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
    client = RESTClient(api_key=api_key, api_secret=api_token)
    return client.get_portfolios()["portfolios"][0]["name"]


async def validate_api(hass: HomeAssistant, data):
    """Validate the credentials."""

    try:
        user = await hass.async_add_executor_job(
            get_user_from_client, data[CONF_API_KEY], data[CONF_API_TOKEN]
        )
    except HTTPError as error:
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

    return {"title": user}


async def validate_options(
    hass: HomeAssistant, config_entry: CoinbaseConfigEntry, options
):
    """Validate the requested resources are provided by API."""

    client = config_entry.runtime_data.client

    accounts = await hass.async_add_executor_job(get_accounts, client)

    accounts_currencies = [
        account[API_ACCOUNT_CURRENCY]
        for account in accounts
        if not account[ACCOUNT_IS_VAULT]
    ]

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

    reauth_entry: CoinbaseConfigEntry

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
            return self.async_create_entry(title=info["title"], data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication flow."""
        self.reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "account_name": self.reauth_entry.title,
                },
                errors=errors,
            )

        try:
            await validate_api(self.hass, user_input)
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
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                data_updates=user_input,
                reason="reauth_successful",
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "account_name": self.reauth_entry.title,
            },
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: CoinbaseConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
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
