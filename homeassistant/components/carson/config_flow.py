"""Config flow for Carson integration."""
import logging

from carson_living import (
    CarsonAuth,
    CarsonAuthenticationError,
    CarsonCommunicationError,
)
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.core import callback

from .const import (  # pylint: disable=unused-import
    CONF_LIST_FROM_EAGLE_EYE,
    DEFAULT_CONF_LIST_FROM_EAGLE_EYE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"username": str, "password": str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    auth = CarsonAuth(data["username"], data["password"])

    try:
        await hass.async_add_executor_job(auth.update_token)
    except CarsonAuthenticationError:
        _LOGGER.warning("Authentication error for %s", data["username"])
        raise InvalidAuth
    except CarsonCommunicationError:
        _LOGGER.warning("Communication error with Carson API.")
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return auth.token


class CarsonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Carson."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                token = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input["username"])

                return self.async_create_entry(
                    title=user_input["username"],
                    data={
                        "username": user_input["username"],
                        "password": user_input["password"],
                        "token": token,
                    },
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return CarsonOptionsFlowHandler(config_entry)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CarsonOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Carson options."""

    def __init__(self, config_entry):
        """Initialize Carson options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the Carson options."""
        return await self.async_step_carson_devices()

    async def async_step_carson_devices(self, user_input=None):
        """Manage the Carson devices options."""
        if user_input is not None:
            self.options[CONF_LIST_FROM_EAGLE_EYE] = user_input[
                CONF_LIST_FROM_EAGLE_EYE
            ]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="carson_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LIST_FROM_EAGLE_EYE,
                        default=self.config_entry.options.get(
                            CONF_LIST_FROM_EAGLE_EYE, DEFAULT_CONF_LIST_FROM_EAGLE_EYE
                        ),
                    ): bool,
                }
            ),
        )
