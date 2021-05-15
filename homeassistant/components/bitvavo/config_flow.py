"""Config flow for Bitvavo integration."""
from __future__ import annotations

import logging

from bitvavo.BitvavoClient import BitvavoClient
from bitvavo.BitvavoExceptions import BitvavoException
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_API_SECRET, CONF_MARKETS, CONF_SHOW_EMPTY_ASSETS, DOMAIN
from .errors import InvalidAuth, InvalidResponse

_LOGGER = logging.getLogger(__name__)


def _markets_schema(markets: list | None):
    """Markets selection schema."""
    markets_dict = {}

    if markets:
        markets_dict = {name: name for name in markets}

    return vol.Schema({vol.Required(CONF_MARKETS): cv.multi_select(markets_dict)})


async def validate_input(hass: HomeAssistant, data: dict):
    """Validate the user input allows us to connect."""
    markets_list = []
    balances_list = []

    api_key = data[CONF_API_KEY]
    api_secret = data[CONF_API_SECRET]

    try:
        client = BitvavoClient(api_key, api_secret)
        markets = await client.get_price_ticker()
        for market in markets:
            markets_list.append(market["market"])
        markets_list.sort()

        balances = await client.get_balance()
        for balance in balances:
            if balance["available"] != "0":
                balances_list.append(balance["symbol"])
        balances_list.sort()
    except BitvavoException as error:
        if str(error.status_code) == "403":
            raise InvalidAuth from error
        raise InvalidResponse from error
    finally:
        await client.close()

    return {"markets": markets_list, "balances": balances_list}


class BitvavoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bitvavo."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the Bitvavo config flow."""
        self.bitvavo_config = {}
        self.markets = None
        self.balances = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return BitvavoOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # assert self.hass

        errors = {}

        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.bitvavo_config.update(user_input)
                self.markets = info["markets"]

                return await self.async_step_markets()

        data_schema = {
            vol.Required(CONF_API_KEY): str,
            vol.Required(CONF_API_SECRET): str,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_markets(self, user_input: dict | None = None):
        """Handle the picking of the markets."""
        errors = {}

        if user_input is not None:
            self.bitvavo_config.update(user_input)
            info, errors = await self._async_validate_or_error(self.bitvavo_config)

            title = "Markets: " + ", ".join(self.bitvavo_config[CONF_MARKETS])

            if not errors:
                await self.async_set_unique_id(user_input[CONF_MARKETS])
                self.balances = info["balances"]

                return self.async_create_entry(title=title, data=self.bitvavo_config)

        return self.async_show_form(
            step_id="markets",
            data_schema=_markets_schema(self.markets),
            errors=errors,
        )

    async def _async_validate_or_error(self, config):
        errors = {}
        info = {}

        try:
            info = await validate_input(self.hass, config)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return info, errors


class BitvavoOptionsFlowHandler(OptionsFlow):
    """Handle Bitvavo options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: ConfigType | None = None):
        """Manage Bitvavo options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SHOW_EMPTY_ASSETS,
                default=self.config_entry.options.get(CONF_SHOW_EMPTY_ASSETS, True),
            ): bool,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
