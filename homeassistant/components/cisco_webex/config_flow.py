"""Config flow for cisco_webex integration."""
import logging

import requests
import voluptuous as vol
import webexteamssdk

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_EMAIL, CONF_TOKEN

from .const import DATA_DISPLAY_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({CONF_TOKEN: str, CONF_EMAIL: str})


class ConfigValidationHub:
    """Methods for config validation."""

    def validate_config(self, api, data) -> bool:
        """Test if auth and email are OK."""

        try:
            try:
                # maybe check here it is a bot token as personal access tokens expire after 12 hours.
                _LOGGER.debug("Authenticating with Webex")
                person_me = api.people.me()
                _LOGGER.debug("Authenticated OK.")
                _LOGGER.debug("api.people.me: %s", person_me)

                if person_me.type != "bot":
                    _LOGGER.error(
                        "Although auth passed, an invalid token type is being used: %s",
                        person_me.type,
                    )
                    raise InvalidAuthTokenType

                email = data[CONF_EMAIL]
                _LOGGER.debug("Searching Webex for people with email: '%s'", email)

                person = next(iter(api.people.list(email=email)), None)
                if person is not None:
                    _LOGGER.debug(
                        "Found person with email: '%s' success. person: %s",
                        email,
                        person,
                    )
                    data[DATA_DISPLAY_NAME] = person.displayName
                    return True
                else:
                    _LOGGER.error("Cannot find any Webex user with email: %s", email)
                    raise EmailNotFound

            except webexteamssdk.ApiError as error:
                _LOGGER.error(error)
                if error.status_code == 400:
                    raise EmailNotFound
                if error.status_code == 401:
                    raise InvalidAuth
                raise error
        except requests.exceptions.ConnectionError as connection_error:
            _LOGGER.error(connection_error)
            raise CannotConnect

        return False


async def validate_token_and_email(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        # pylint: disable=no-value-for-parameter
        vol.Email()(data[CONF_EMAIL])
    except vol.error.EmailInvalid:
        raise InvalidEmail

    hub = ConfigValidationHub()
    api = webexteamssdk.WebexTeamsAPI(access_token=data[CONF_TOKEN])
    data[DATA_DISPLAY_NAME] = "unknown"

    await hass.async_add_executor_job(hub.validate_config, api, data)

    # Return info that you want to store in the config entry.
    return {"title": f"{data[DATA_DISPLAY_NAME]} - {data[CONF_EMAIL]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for cisco_webex."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        description_placeholders = {
            "bot_docs_url": "https://developer.webex.com/docs/bots"
        }
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                description_placeholders=description_placeholders,
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        # Check if already configured
        await self.async_set_unique_id(f"webex_{user_input[CONF_EMAIL]}")
        self._abort_if_unique_id_configured(reload_on_update=True, updates=user_input)

        errors = {}

        try:
            info = await validate_token_and_email(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidAuthTokenType:
            errors["base"] = "invalid_auth_token_type"
        except EmailNotFound:
            errors["base"] = "email_not_found"
        except InvalidEmail:
            errors["base"] = "invalid_email"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            description_placeholders=description_placeholders,
            data_schema=vol.Schema(
                # recycle the bad values. One of them might be OK.
                {
                    vol.Required(CONF_TOKEN, default=user_input[CONF_TOKEN]): str,
                    vol.Required(CONF_EMAIL, default=user_input[CONF_EMAIL]): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidAuthTokenType(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth token type."""


class InvalidEmail(exceptions.HomeAssistantError):
    """Error to indicate there is invalid email."""


class EmailNotFound(exceptions.HomeAssistantError):
    """Error to indicate email is not known to webex."""
