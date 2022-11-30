"""Config flow for August integration."""
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from yalexs.authenticator import ValidationResult

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_LOGIN_METHOD, DOMAIN, LOGIN_METHODS, VERIFICATION_CODE_KEY
from .exceptions import CannotConnect, InvalidAuth, RequireValidation
from .gateway import AugustGateway

_LOGGER = logging.getLogger(__name__)


async def async_validate_input(data, august_gateway):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.

    Request configuration steps from the user.
    """
    if (code := data.get(VERIFICATION_CODE_KEY)) is not None:
        result = await august_gateway.authenticator.async_validate_verification_code(
            code
        )
        _LOGGER.debug("Verification code validation: %s", result)
        if result != ValidationResult.VALIDATED:
            raise RequireValidation

    try:
        await august_gateway.async_authenticate()
    except RequireValidation:
        _LOGGER.debug(
            "Requesting new verification code for %s via %s",
            data.get(CONF_USERNAME),
            data.get(CONF_LOGIN_METHOD),
        )
        if code is None:
            await august_gateway.authenticator.async_send_verification_code()
        raise

    return {
        "title": data.get(CONF_USERNAME),
        "data": august_gateway.config_entry(),
    }


class AugustConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for August."""

    VERSION = 1

    def __init__(self):
        """Store an AugustGateway()."""
        self._august_gateway = None
        self._user_auth_details = {}
        self._needs_reset = False
        self._mode = None
        super().__init__()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        self._august_gateway = AugustGateway(self.hass)
        return await self.async_step_user_validate()

    async def async_step_user_validate(self, user_input=None):
        """Handle authentication."""
        errors = {}
        if user_input is not None:
            result = await self._async_auth_or_validate(user_input, errors)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user_validate",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOGIN_METHOD,
                        default=self._user_auth_details.get(CONF_LOGIN_METHOD, "phone"),
                    ): vol.In(LOGIN_METHODS),
                    vol.Required(
                        CONF_USERNAME,
                        default=self._user_auth_details.get(CONF_USERNAME),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_validation(self, user_input=None):
        """Handle validation (2fa) step."""
        if user_input:
            if self._mode == "reauth":
                return await self.async_step_reauth_validate(user_input)
            return await self.async_step_user_validate(user_input)

        return self.async_show_form(
            step_id="validation",
            data_schema=vol.Schema(
                {vol.Required(VERIFICATION_CODE_KEY): vol.All(str, vol.Strip)}
            ),
            description_placeholders={
                CONF_USERNAME: self._user_auth_details[CONF_USERNAME],
                CONF_LOGIN_METHOD: self._user_auth_details[CONF_LOGIN_METHOD],
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._user_auth_details = dict(entry_data)
        self._mode = "reauth"
        self._needs_reset = True
        self._august_gateway = AugustGateway(self.hass)
        return await self.async_step_reauth_validate()

    async def async_step_reauth_validate(self, user_input=None):
        """Handle reauth and validation."""
        errors = {}
        if user_input is not None:
            result = await self._async_auth_or_validate(user_input, errors)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reauth_validate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                CONF_USERNAME: self._user_auth_details[CONF_USERNAME],
            },
        )

    async def _async_auth_or_validate(self, user_input, errors):
        self._user_auth_details.update(user_input)
        await self._august_gateway.async_setup(self._user_auth_details)
        if self._needs_reset:
            self._needs_reset = False
            await self._august_gateway.async_reset_authentication()
        try:
            info = await async_validate_input(
                self._user_auth_details,
                self._august_gateway,
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except RequireValidation:
            return await self.async_step_validation()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return None

        existing_entry = await self.async_set_unique_id(
            self._user_auth_details[CONF_USERNAME]
        )
        if not existing_entry:
            return self.async_create_entry(title=info["title"], data=info["data"])

        self.hass.config_entries.async_update_entry(existing_entry, data=info["data"])
        await self.hass.config_entries.async_reload(existing_entry.entry_id)
        return self.async_abort(reason="reauth_successful")
