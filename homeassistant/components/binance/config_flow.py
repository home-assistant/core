"""Config flow for Binance integration."""
from __future__ import annotations

import logging

from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_API_SECRET, CONF_MARKETS
from .const import DOMAIN  # pylint:disable=unused-import
from .errors import InvalidAuth, InvalidResponse

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_SECRET): str,
    }
)


def _markets_schema(markets: list | None = None):
    """Markets selection schema."""
    markets_dict = {}

    if markets:
        markets_dict = {name: name for name in markets}

    return vol.Schema({vol.Required(CONF_MARKETS): cv.multi_select(markets_dict)})


async def validate_input(hass: HomeAssistant, data: dict):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    markets_list = []
    balances_list = []

    api_key = data[CONF_API_KEY]
    api_secret = data[CONF_API_SECRET]

    try:
        binance = await AsyncClient.create(api_key=api_key, api_secret=api_secret)

        markets = await binance.get_all_tickers()
        for market in markets:
            markets_list.append(market["symbol"])
        markets_list.sort()

        balances = await binance.get_account()
        for balance in balances["balances"]:
            if balance["free"] > "0.00000000":
                balances_list.append(balance["asset"])
        balances_list.sort()
    except BinanceAPIException as error:
        if (
            error.message == "Invalid API-key, IP, or permissions for action."
            or error.message == "API-key format invalid."
        ):
            raise InvalidAuth from error
        raise InvalidResponse from error
    except BinanceRequestException as error:
        raise InvalidResponse from error
    finally:
        await binance.close_connection()

    return {"markets": markets_list, "balances": balances_list}


class BinanceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Binance."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the Binance config flow."""
        self.binance_config = {}
        self.markets = None
        self.balances = None

    async def async_step_user(self, user_input: dict | None = None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        assert self.hass

        errors = {}

        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.binance_config.update(user_input)
                self.markets = info["markets"]

                return await self.async_step_markets()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_markets(self, user_input: dict | None = None):
        """Handle the picking of the markets."""
        errors = {}

        if user_input is not None:
            self.binance_config.update(user_input)
            info, errors = await self._async_validate_or_error(self.binance_config)

            title = "Markets: " + ", ".join(self.binance_config[CONF_MARKETS])

            if not errors:
                await self.async_set_unique_id(user_input[CONF_MARKETS])
                self.balances = info["balances"]

                return self.async_create_entry(title=title, data=self.binance_config)

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
        except InvalidResponse:
            errors["base"] = "invalid_response"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return info, errors
