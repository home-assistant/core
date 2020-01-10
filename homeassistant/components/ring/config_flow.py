"""Config flow for Ring integration."""
from functools import partial
import logging

from oauthlib.oauth2 import AccessDeniedError
from ring_doorbell import Ring
import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from . import DEFAULT_CACHEDB, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    cache = hass.config.path(DEFAULT_CACHEDB)

    def otp_callback():
        if "2fa" in data:
            return data["2fa"]

        raise Require2FA

    try:
        ring = await hass.async_add_executor_job(
            partial(
                Ring,
                username=data["username"],
                password=data["password"],
                cache_file=cache,
                auth_callback=otp_callback,
            )
        )
    except AccessDeniedError:
        raise InvalidAuth

    if not ring.is_connected:
        raise InvalidAuth


class RingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ring."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    user_pass = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input["username"])

                return self.async_create_entry(
                    title=user_input["username"],
                    data={"username": user_input["username"]},
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

    async def async_step_import(self, user_input):
        """Handle import."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(user_input)


class Require2FA(exceptions.HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
