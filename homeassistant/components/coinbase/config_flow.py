"""Config flow for Coinbase integration."""
from __future__ import annotations

import logging

from coinbase.wallet.client import Client
from coinbase.wallet.error import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import get_accounts
from .const import (
    API_ACCOUNT_CURRENCY,
    API_RATES,
    API_RESOURCE_TYPE,
    API_TYPE_VAULT,
    CONF_CURRENCIES,
    CONF_EXCHANGE_BASE,
    CONF_EXCHANGE_PRECISION,
    CONF_EXCHANGE_PRECISION_DEFAULT,
    CONF_EXCHANGE_RATES,
    CONF_OPTIONS,
    CONF_YAML_API_TOKEN,
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
    client = Client(api_key, api_token)
    user = client.get_current_user()
    return user


async def validate_api(hass: core.HomeAssistant, data):
    """Validate the credentials."""

    try:
        user = await hass.async_add_executor_job(
            get_user_from_client, data[CONF_API_KEY], data[CONF_API_TOKEN]
        )
    except AuthenticationError as error:
        if "api key" in str(error):
            _LOGGER.debug("Coinbase rejected API credentials due to an invalid API key")
            raise InvalidKey from error
        if "invalid signature" in str(error):
            _LOGGER.debug(
                "Coinbase rejected API credentials due to an invalid API secret"
            )
            raise InvalidSecret from error
        _LOGGER.debug("Coinbase rejected API credentials due to an unknown error")
        raise InvalidAuth from error
    except ConnectionError as error:
        raise CannotConnect from error

    return {"title": user["name"]}


async def validate_options(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry, options
):
    """Validate the requested resources are provided by API."""

    client = hass.data[DOMAIN][config_entry.entry_id].client

    accounts = await hass.async_add_executor_job(get_accounts, client)

    accounts_currencies = [
        account[API_ACCOUNT_CURRENCY]
        for account in accounts
        if account[API_RESOURCE_TYPE] != API_TYPE_VAULT
    ]
    available_rates = await hass.async_add_executor_job(client.get_exchange_rates)
    if CONF_CURRENCIES in options:
        for currency in options[CONF_CURRENCIES]:
            if currency not in accounts_currencies:
                raise CurrencyUnavailable

    if CONF_EXCHANGE_RATES in options:
        for rate in options[CONF_EXCHANGE_RATES]:
            if rate not in available_rates[API_RATES]:
                raise ExchangeRateUnavailable

    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coinbase."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})

        options = {}

        if CONF_OPTIONS in user_input:
            options = user_input.pop(CONF_OPTIONS)

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
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=info["title"], data=user_input, options=options
            )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, config):
        """Handle import of Coinbase config from YAML."""

        cleaned_data = {
            CONF_API_KEY: config[CONF_API_KEY],
            CONF_API_TOKEN: config[CONF_YAML_API_TOKEN],
        }
        cleaned_data[CONF_OPTIONS] = {
            CONF_CURRENCIES: [],
            CONF_EXCHANGE_RATES: [],
        }
        if CONF_CURRENCIES in config:
            cleaned_data[CONF_OPTIONS][CONF_CURRENCIES] = config[CONF_CURRENCIES]
        if CONF_EXCHANGE_RATES in config:
            cleaned_data[CONF_OPTIONS][CONF_EXCHANGE_RATES] = config[
                CONF_EXCHANGE_RATES
            ]

        return await self.async_step_user(user_input=cleaned_data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Coinbase."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
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
            except Exception:  # pylint: disable=broad-except
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidSecret(exceptions.HomeAssistantError):
    """Error to indicate auth failed due to invalid secret."""


class InvalidKey(exceptions.HomeAssistantError):
    """Error to indicate auth failed due to invalid key."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate Coinbase API Key is already configured."""


class CurrencyUnavailable(exceptions.HomeAssistantError):
    """Error to indicate the requested currency resource is not provided by the API."""


class ExchangeRateUnavailable(exceptions.HomeAssistantError):
    """Error to indicate the requested exchange rate resource is not provided by the API."""
