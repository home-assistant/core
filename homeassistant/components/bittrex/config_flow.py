"""Config flow for Bittrex integration."""
import logging
from typing import Dict, List, Optional

from aiobittrexapi import Bittrex
from aiobittrexapi.errors import (
    BittrexApiError,
    BittrexInvalidAuthentication,
    BittrexResponseError,
)
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_API_SECRET, CONF_BALANCES, CONF_MARKETS
from .const import DOMAIN  # pylint:disable=unused-import
from .errors import CannotConnect, InvalidAuth, InvalidResponse

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_API_SECRET): str,
    }
)


def _markets_schema(markets: Optional[List] = None):
    """Markets selection schema."""
    markets_dict = {}

    if markets:
        markets_dict = {name: name for name in markets}

    return vol.Schema({vol.Required(CONF_MARKETS): cv.multi_select(markets_dict)})


def _balances_schema(balances: Optional[List] = None):
    """Balances selection schema."""
    balances_dict = {}

    if balances:
        balances_dict = {name: name for name in balances}

    return vol.Schema({vol.Optional(CONF_BALANCES): cv.multi_select(balances_dict)})


async def validate_input(hass: HomeAssistant, data: Dict):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    markets_list = []
    balances_list = []

    api_key = data[CONF_API_KEY]
    api_secret = data[CONF_API_SECRET]

    try:
        bittrex = Bittrex(api_key, api_secret)
        await bittrex.get_account()

        markets = await bittrex.get_markets()
        for market in markets:
            markets_list.append(market["symbol"])

        balances = await bittrex.get_balances()
        for balance in balances:
            balances_list.append(balance)
    except BittrexInvalidAuthentication as error:
        raise InvalidAuth from error
    except BittrexApiError as error:
        raise CannotConnect from error
    except BittrexResponseError as error:
        raise InvalidResponse from error
    finally:
        await bittrex.close()

    return {"markets": markets_list, "balances": balances_list}


class BittrexConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bittrex."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the Bittrex config flow."""
        self.bittrex_config = {}
        self.markets = None
        self.balances = None

    async def async_step_user(self, user_input: Optional[Dict] = None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        assert self.hass

        errors = {}

        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.bittrex_config.update(user_input)
                self.markets = info["markets"]

                return await self.async_step_markets()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_markets(self, user_input: Optional[Dict] = None):
        """Handle the picking of the markets."""
        errors = {}

        if user_input is not None:
            self.bittrex_config.update(user_input)
            info, errors = await self._async_validate_or_error(self.bittrex_config)

            if not errors:
                await self.async_set_unique_id(user_input[CONF_MARKETS])
                self.balances = info["balances"]

                return await self.async_step_balances()

        return self.async_show_form(
            step_id="markets",
            data_schema=_markets_schema(self.markets),
            errors=errors,
        )

    async def async_step_balances(self, user_input: Optional[Dict] = None):
        """Handle the picking of the balances."""
        errors = {}

        if user_input is not None:
            self.bittrex_config.update(user_input)
            title = "Markets: " + ", ".join(self.bittrex_config[CONF_MARKETS])

            if CONF_BALANCES in self.bittrex_config:
                title = (
                    title
                    + " - "
                    + "Balances: "
                    + ", ".join(self.bittrex_config[CONF_BALANCES])
                )

            return self.async_create_entry(title=title, data=self.bittrex_config)

        return self.async_show_form(
            step_id="balances",
            data_schema=_balances_schema(self.balances),
            errors=errors,
        )

    async def _async_validate_or_error(self, config):
        errors = {}
        info = {}

        try:
            info = await validate_input(self.hass, config)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidResponse:
            errors["base"] = "invalid_response"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return info, errors
