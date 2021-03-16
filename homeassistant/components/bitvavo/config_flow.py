"""Config flow for Bitvavo integration."""
import logging
from typing import Dict, List, Optional

from cryptoxlib.CryptoXLib import CryptoXLib
from cryptoxlib.clients.bitvavo.exceptions import BitvavoException
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


def _markets_schema(markets: Optional[List] = None):
    """Markets selection schema."""
    markets_dict = {}

    if markets:
        markets_dict = {name: name for name in markets}

    return vol.Schema({vol.Required(CONF_MARKETS): cv.multi_select(markets_dict)})


async def validate_input(hass: HomeAssistant, data: Dict):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    markets_list = []
    balances_list = []

    api_key = data[CONF_API_KEY]
    api_secret = data[CONF_API_SECRET]

    try:
        client = CryptoXLib.create_bitvavo_client(api_key, api_secret)

        markets = (await client.get_price_ticker())["response"]
        for market in markets:
            markets_list.append(market["market"])
        markets_list.sort()

        balances = (await client.get_balance())["response"]
        for balance in balances:
            if balance["available"] != "0":
                balances_list.append(balance["symbol"])
        balances_list.sort()
    except BitvavoException as error:
        raise InvalidAuth from error
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

    async def async_step_user(self, user_input: Optional[Dict] = None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        assert self.hass

        errors = {}

        if user_input is not None:
            info, errors = await self._async_validate_or_error(user_input)

            if not errors:
                self.bitvavo_config.update(user_input)
                self.markets = info["markets"]

                return await self.async_step_markets()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_markets(self, user_input: Optional[Dict] = None):
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