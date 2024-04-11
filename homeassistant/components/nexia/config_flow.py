"""Config flow for Nexia integration."""

import logging

import aiohttp
from nexia.const import BRAND_ASAIR, BRAND_NEXIA, BRAND_TRANE
from nexia.home import NexiaHome
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BRAND_ASAIR_NAME,
    BRAND_NEXIA_NAME,
    BRAND_TRANE_NAME,
    CONF_BRAND,
    DOMAIN,
)
from .util import is_invalid_auth_code

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_BRAND, default=BRAND_NEXIA): vol.In(
            {
                BRAND_NEXIA: BRAND_NEXIA_NAME,
                BRAND_ASAIR: BRAND_ASAIR_NAME,
                BRAND_TRANE: BRAND_TRANE_NAME,
            }
        ),
    }
)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    state_file = hass.config.path(
        f"{data[CONF_BRAND]}_config_{data[CONF_USERNAME]}.conf"
    )
    session = async_get_clientsession(hass)
    nexia_home = NexiaHome(
        session,
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        brand=data[CONF_BRAND],
        device_name=hass.config.location_name,
        state_file=state_file,
    )
    try:
        await nexia_home.login()
    except TimeoutError as ex:
        _LOGGER.error("Unable to connect to Nexia service: %s", ex)
        raise CannotConnect from ex
    except aiohttp.ClientResponseError as http_ex:
        _LOGGER.error("HTTP error from Nexia service: %s", http_ex)
        if is_invalid_auth_code(http_ex.status):
            raise InvalidAuth from http_ex
        raise CannotConnect from http_ex

    if not nexia_home.get_name():
        raise InvalidAuth

    info = {"title": nexia_home.get_name(), "house_id": nexia_home.house_id}
    _LOGGER.debug("Setup ok with info: %s", info)
    return info


class NexiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nexia."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(info["house_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
