"""Config flow to configure StarLine component."""

from __future__ import annotations

from starline import StarlineAuth
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import (
    _LOGGER,
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_CAPTCHA_CODE,
    CONF_MFA_CODE,
    DATA_EXPIRES,
    DATA_SLID_TOKEN,
    DATA_SLNET_TOKEN,
    DATA_USER_ID,
    DOMAIN,
    ERROR_AUTH_APP,
    ERROR_AUTH_MFA,
    ERROR_AUTH_USER,
)


class StarlineFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a StarLine config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._app_id: str | None = None
        self._app_secret: str | None = None
        self._username: str | None = None
        self._password: str | None = None
        self._mfa_code: str | None = None

        self._app_code = None
        self._app_token = None
        self._user_slid = None
        self._user_id = None
        self._slnet_token = None
        self._slnet_token_expires = None
        self._captcha_image = None
        self._captcha_sid = None
        self._captcha_code = None
        self._phone_number = None

        self._auth = StarlineAuth()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_auth_app(user_input)

    async def async_step_auth_app(self, user_input=None, error=None):
        """Authenticate application step."""
        if user_input is not None:
            self._app_id = user_input[CONF_APP_ID]
            self._app_secret = user_input[CONF_APP_SECRET]
            return await self._async_authenticate_app(error)
        return self._async_form_auth_app(error)

    async def async_step_auth_user(self, user_input=None, error=None):
        """Authenticate user step."""
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            return await self._async_authenticate_user(error)
        return self._async_form_auth_user(error)

    async def async_step_auth_mfa(self, user_input=None, error=None):
        """Authenticate mfa step."""
        if user_input is not None:
            self._mfa_code = user_input[CONF_MFA_CODE]
            return await self._async_authenticate_user(error)
        return self._async_form_auth_mfa(error)

    async def async_step_auth_captcha(self, user_input=None, error=None):
        """Captcha verification step."""
        if user_input is not None:
            self._captcha_code = user_input[CONF_CAPTCHA_CODE]
            return await self._async_authenticate_user(error)
        return self._async_form_auth_captcha(error)

    @callback
    def _async_form_auth_app(self, error=None):
        """Authenticate application form."""
        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="auth_app",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_APP_ID, default=self._app_id or vol.UNDEFINED
                    ): str,
                    vol.Required(
                        CONF_APP_SECRET, default=self._app_secret or vol.UNDEFINED
                    ): str,
                }
            ),
            errors=errors,
        )

    @callback
    def _async_form_auth_user(self, error=None):
        """Authenticate user form."""
        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="auth_user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=self._username or vol.UNDEFINED
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=self._password or vol.UNDEFINED
                    ): str,
                }
            ),
            errors=errors,
        )

    @callback
    def _async_form_auth_mfa(self, error=None):
        """Authenticate mfa form."""
        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="auth_mfa",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MFA_CODE, default=self._mfa_code or vol.UNDEFINED
                    ): str
                }
            ),
            errors=errors,
            description_placeholders={"phone_number": self._phone_number},
        )

    @callback
    def _async_form_auth_captcha(self, error=None):
        """Captcha verification form."""
        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="auth_captcha",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CAPTCHA_CODE, default=self._captcha_code or vol.UNDEFINED
                    ): str
                }
            ),
            errors=errors,
            description_placeholders={
                "captcha_img": '<img src="' + self._captcha_image + '"/>'
            },
        )

    async def _async_authenticate_app(self, error=None):
        """Authenticate application."""
        try:
            self._app_code = await self.hass.async_add_executor_job(
                self._auth.get_app_code, self._app_id, self._app_secret
            )
            self._app_token = await self.hass.async_add_executor_job(
                self._auth.get_app_token, self._app_id, self._app_secret, self._app_code
            )
            return self._async_form_auth_user(error)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error auth StarLine: %s", err)
            return self._async_form_auth_app(ERROR_AUTH_APP)

    async def _async_authenticate_user(self, error=None):
        """Authenticate user."""
        try:
            state, data = await self.hass.async_add_executor_job(
                self._auth.get_slid_user_token,
                self._app_token,
                self._username,
                self._password,
                self._mfa_code,
                self._captcha_sid,
                self._captcha_code,
            )

            if state == 1:
                self._user_slid = data["user_token"]
                return await self._async_get_entry()

            if "phone" in data:
                self._phone_number = data["phone"]
                if state == 0:
                    error = ERROR_AUTH_MFA
                return self._async_form_auth_mfa(error)

            if "captchaSid" in data:
                self._captcha_sid = data["captchaSid"]
                self._captcha_image = data["captchaImg"]
                return self._async_form_auth_captcha(error)

            #  pylint: disable=broad-exception-raised
            raise Exception(data)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error auth user: %s", err)
            return self._async_form_auth_user(ERROR_AUTH_USER)

    async def _async_get_entry(self):
        """Create entry."""
        (
            self._slnet_token,
            self._slnet_token_expires,
            self._user_id,
        ) = await self.hass.async_add_executor_job(
            self._auth.get_user_id, self._user_slid
        )

        return self.async_create_entry(
            title=f"Application {self._app_id}",
            data={
                DATA_USER_ID: self._user_id,
                DATA_SLNET_TOKEN: self._slnet_token,
                DATA_SLID_TOKEN: self._user_slid,
                DATA_EXPIRES: self._slnet_token_expires,
            },
        )
