"""Config flow for August integration."""
import logging

from august.authenticator import ValidationResult
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME

from .const import (
    CONF_LOGIN_METHOD,
    DEFAULT_TIMEOUT,
    LOGIN_METHODS,
    VERIFICATION_CODE_KEY,
)
from .const import DOMAIN  # pylint:disable=unused-import
from .exceptions import CannotConnect, InvalidAuth, RequireValidation
from .gateway import AugustGateway

_LOGGER = logging.getLogger(__name__)


async def async_validate_input(
    data,
    august_gateway,
):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.

    Request configuration steps from the user.
    """

    code = data.get(VERIFICATION_CODE_KEY)

    if code is not None:
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
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Store an AugustGateway()."""
        self._august_gateway = None
        self.user_auth_details = {}
        self._needs_reset = False
        super().__init__()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._august_gateway is None:
            self._august_gateway = AugustGateway(self.hass)
        errors = {}
        if user_input is not None:
            combined_inputs = {**self.user_auth_details, **user_input}
            await self._august_gateway.async_setup(combined_inputs)
            if self._needs_reset:
                self._needs_reset = False
                await self._august_gateway.async_reset_authentication()

            try:
                info = await async_validate_input(
                    combined_inputs,
                    self._august_gateway,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except RequireValidation:
                self.user_auth_details.update(user_input)

                return await self.async_step_validation()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                self.user_auth_details.update(user_input)

                existing_entry = await self.async_set_unique_id(
                    combined_inputs[CONF_USERNAME]
                )
                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=info["data"]
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                return self.async_create_entry(title=info["title"], data=info["data"])

        return self.async_show_form(
            step_id="user", data_schema=self._async_build_schema(), errors=errors
        )

    async def async_step_validation(self, user_input=None):
        """Handle validation (2fa) step."""
        if user_input:
            return await self.async_step_user({**self.user_auth_details, **user_input})

        return self.async_show_form(
            step_id="validation",
            data_schema=vol.Schema(
                {vol.Required(VERIFICATION_CODE_KEY): vol.All(str, vol.Strip)}
            ),
            description_placeholders={
                CONF_USERNAME: self.user_auth_details.get(CONF_USERNAME),
                CONF_LOGIN_METHOD: self.user_auth_details.get(CONF_LOGIN_METHOD),
            },
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        return await self.async_step_user(user_input)

    async def async_step_reauth(self, data):
        """Handle configuration by re-auth."""
        self.user_auth_details = dict(data)
        self._needs_reset = True
        return await self.async_step_user()

    def _async_build_schema(self):
        """Generate the config flow schema."""
        base_schema = {
            vol.Required(CONF_LOGIN_METHOD, default="phone"): vol.In(LOGIN_METHODS),
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
        }
        for key in self.user_auth_details:
            if key == CONF_PASSWORD or key not in base_schema:
                continue
            del base_schema[key]
        return vol.Schema(base_schema)
