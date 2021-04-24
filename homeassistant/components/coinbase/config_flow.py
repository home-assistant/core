"""Config flow for Coinbase integration."""
import logging

from coinbase.wallet.client import Client
from coinbase.wallet.error import AuthenticationError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN

from .const import (
    API_ACCOUNT_CURRENCY,
    API_ACCOUNTS_DATA,
    API_RATES,
    CONF_CURRENCIES,
    CONF_EXCHANGE_RATES,
    CONF_YAML_API_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_CURRENCIES): str,
        vol.Optional(CONF_EXCHANGE_RATES): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the credentials and requested resources."""

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_API_KEY] == data[CONF_API_KEY]:
            raise AlreadyConfigured
    try:
        client = await hass.async_add_executor_job(
            Client, data[CONF_API_KEY], data[CONF_API_TOKEN]
        )
        user = await hass.async_add_executor_job(client.get_current_user)
    except AuthenticationError as error:
        raise InvalidAuth from error
    except ConnectionError as error:
        raise CannotConnect from error

    accounts = await hass.async_add_executor_job(client.get_accounts)
    accounts_currencies = [
        account[API_ACCOUNT_CURRENCY] for account in accounts[API_ACCOUNTS_DATA]
    ]
    available_rates = await hass.async_add_executor_job(client.get_exchange_rates)
    if CONF_CURRENCIES in data:
        for currency in data[CONF_CURRENCIES]:
            if currency not in accounts_currencies:
                raise CurrencyUnavaliable

    if CONF_EXCHANGE_RATES in data:
        for rate in data[CONF_EXCHANGE_RATES]:
            if rate not in available_rates[API_RATES]:
                raise ExchangeRateUnavaliable

    return {"title": user["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coinbase."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            if CONF_CURRENCIES in user_input:
                user_input[CONF_CURRENCIES] = (
                    user_input[CONF_CURRENCIES].upper().replace(" ", "").split(",")
                )
            if CONF_EXCHANGE_RATES in user_input:
                user_input[CONF_EXCHANGE_RATES] = (
                    user_input[CONF_EXCHANGE_RATES].upper().replace(" ", "").split(",")
                )
            info = await validate_input(self.hass, user_input)
        except AlreadyConfigured:
            return self.async_abort(reason="already_configured")
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except CurrencyUnavaliable:
            errors["base"] = "currency_unavaliable"
        except ExchangeRateUnavaliable:
            errors["base"] = "exchange_rate_unavaliable"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=info["title"],
                data=user_input,
            )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, config):
        """Handle import of Coinbase config from YAML."""
        cleaned_data = {}
        cleaned_data[CONF_API_KEY] = config[CONF_API_KEY]
        cleaned_data[CONF_API_TOKEN] = config[CONF_YAML_API_TOKEN]
        if CONF_CURRENCIES in config:
            cleaned_data[CONF_CURRENCIES] = ",".join(config[CONF_CURRENCIES])
        if CONF_EXCHANGE_RATES in config:
            cleaned_data[CONF_EXCHANGE_RATES] = ",".join(config[CONF_EXCHANGE_RATES])

        return await self.async_step_user(user_input=cleaned_data)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate Coinbase API Key is already configured."""


class CurrencyUnavaliable(exceptions.HomeAssistantError):
    """Error to indicate the requested currency resource is not provided by the API."""


class ExchangeRateUnavaliable(exceptions.HomeAssistantError):
    """Error to indicate the requested exchange rate resource is not provided by the API."""
