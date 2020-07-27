"""Config flow for Ring integration."""
import logging

from oauthlib.oauth2 import AccessDeniedError, MissingTokenError
from ring_doorbell import Auth
import voluptuous as vol

from homeassistant import config_entries, const, core, exceptions

from . import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    auth = Auth(f"HomeAssistant/{const.__version__}")

    try:
        token = await hass.async_add_executor_job(
            auth.fetch_token, data["username"], data["password"], data.get("2fa"),
        )
    except MissingTokenError:
        raise Require2FA
    except AccessDeniedError:
        raise InvalidAuth

    return token


class RingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    user_pass = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                token = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input["username"])

                return self.async_create_entry(
                    title=user_input["username"],
                    data={"username": user_input["username"], "token": token},
                )
            except Require2FA:
                self.user_pass = user_input

                return await self.async_step_2fa()

            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({"username": str, "password": str}),
            errors=errors,
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2fa step."""
        if user_input:
            return await self.async_step_user({**self.user_pass, **user_input})

        return self.async_show_form(
            step_id="2fa", data_schema=vol.Schema({"2fa": str}),
        )


class Require2FA(exceptions.HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
