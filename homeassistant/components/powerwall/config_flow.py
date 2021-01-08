"""Config flow for Tesla Powerwall integration."""
import logging

from tesla_powerwall import MissingAttributeError, Powerwall, PowerwallUnreachableError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_IP_ADDRESS

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    power_wall = Powerwall(data[CONF_IP_ADDRESS])

    try:
        await hass.async_add_executor_job(power_wall.detect_and_pin_version)
        site_info = await hass.async_add_executor_job(power_wall.get_site_info)
    except PowerwallUnreachableError as err:
        raise CannotConnect from err
    except MissingAttributeError as err:
        # Only log the exception without the traceback
        _LOGGER.error(str(err))
        raise WrongVersion from err

    # Return info that you want to store in the config entry.
    return {"title": site_info.site_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla Powerwall."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except WrongVersion:
                errors["base"] = "wrong_version"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
        self._abort_if_unique_id_configured()

        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class WrongVersion(exceptions.HomeAssistantError):
    """Error to indicate the powerwall uses a software version we cannot interact with."""
