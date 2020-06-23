"""
Config Flow for Wiser Rooms.

https://github.com/asantaga/wiserHomeAssistantPlatform
@msp1974

"""
import requests.exceptions
import voluptuous as vol
from wiserHeatingAPI.wiserHub import (
    WiserHubAuthenticationException,
    WiserHubTimeoutException,
    WiserRESTException,
    wiserHub,
)

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .const import (
    _LOGGER,
    CONF_BOOST_TEMP,
    CONF_BOOST_TEMP_TIME,
    DEFAULT_BOOST_TEMP,
    DEFAULT_BOOST_TEMP_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(hass, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    try:
        wiser = await hass.async_add_executor_job(
            wiserHub, data[CONF_HOST], data[CONF_PASSWORD]
        )
        wiser_id = await hass.async_add_executor_job(wiser.getWiserHubName)

    except WiserHubTimeoutException:
        raise CannotConnect
    except WiserHubAuthenticationException:
        raise InvalidAuth
    except WiserRESTException:
        raise UnknownError
    except requests.exceptions.ConnectionError:
        raise CannotConnect
    except RuntimeError:
        raise UnknownError

    unique_id = str(f"{DOMAIN}-{wiser_id}")
    name = wiser_id

    return {"title": name, "unique_id": unique_id}


@config_entries.HANDLERS.register(DOMAIN)
class WiserFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """
    WiserFlowHandler configuration method.

    The schema version of the entries that it creates
    Home Assistant will call your migrate method if the version changes
    (this is not implemented yet)
    """

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the wiser flow."""
        self.discovery_schema = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return flow options."""
        return WiserOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """
        Handle a Wiser Heat Hub config flow start.

        Manage device specific parameters.
        """
        errors = {}
        if user_input is not None:
            try:
                validated = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "auth_failure"
            except CannotConnect:
                errors["base"] = "timeout_error"
            except UnknownError:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                await self.async_set_unique_id(validated["unique_id"])
                self._abort_if_unique_id_configured()

                # Add hub name to config
                user_input[CONF_NAME] = validated["title"]
                return self.async_create_entry(
                    title=validated["title"], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.discovery_schema or DATA_SCHEMA,
            errors=errors,
        )


class WiserOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for wiser hub."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BOOST_TEMP,
                    default=self.config_entry.options.get(
                        CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP
                    ),
                ): int,
                vol.Optional(
                    CONF_BOOST_TEMP_TIME,
                    default=self.config_entry.options.get(
                        CONF_BOOST_TEMP_TIME, DEFAULT_BOOST_TEMP_TIME
                    ),
                ): int,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class UnknownError(exceptions.HomeAssistantError):
    """Error to indicate there is an unknown error."""
