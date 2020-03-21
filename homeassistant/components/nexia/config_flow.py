"""Config flow for Nexia integration."""
import logging

from nexia.home import NexiaHome
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({CONF_USERNAME: str, CONF_PASSWORD: str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        nexia_home = NexiaHome(
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            auto_login=False,
            auto_update=False,
            device_name=hass.config.location_name,
        )
        await hass.async_add_executor_job(nexia_home.login)
    except ConnectTimeout as ex:
        _LOGGER.error("Unable to connect to Nexia service: %s", ex)
        raise CannotConnect
    except HTTPError as http_ex:
        _LOGGER.error("HTTP error from Nexia service: %s", http_ex)
        if http_ex.response.status_code >= 400 and http_ex.response.status_code < 500:
            raise InvalidAuth
        raise CannotConnect

    if not nexia_home.get_name():
        raise InvalidAuth

    info = {"title": nexia_home.get_name(), "house_id": nexia_home.house_id}
    _LOGGER.debug("Setup ok with info: %s", info)
    return info


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nexia."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
