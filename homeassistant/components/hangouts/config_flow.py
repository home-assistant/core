"""Config flow to configure Google Hangouts."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback

from .const import CONF_2FA, CONF_REFRESH_TOKEN, DOMAIN as HANGOUTS_DOMAIN


@callback
def configured_hangouts(hass):
    """Return the configures Google Hangouts Account."""
    entries = hass.config_entries.async_entries(HANGOUTS_DOMAIN)
    if entries:
        return entries[0]
    return None


@config_entries.HANDLERS.register(HANGOUTS_DOMAIN)
class HangoutsFlowHandler(config_entries.ConfigFlow):
    """Config flow Google Hangouts."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize Google Hangouts config flow."""
        self._credentials = None
        self._refresh_token = None

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if configured_hangouts(self.hass) is not None:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            from hangups import get_auth
            from .hangups_utils import (HangoutsCredentials,
                                        HangoutsRefreshToken,
                                        GoogleAuthError, Google2FAError)
            self._credentials = HangoutsCredentials(user_input[CONF_EMAIL],
                                                    user_input[CONF_PASSWORD])
            self._refresh_token = HangoutsRefreshToken(None)
            try:
                await self.hass.async_add_executor_job(get_auth,
                                                       self._credentials,
                                                       self._refresh_token)

                return await self.async_step_final()
            except GoogleAuthError as err:
                if isinstance(err, Google2FAError):
                    return await self.async_step_2fa()
                msg = str(err)
                if msg == 'Unknown verification code input':
                    errors['base'] = 'invalid_2fa_method'
                else:
                    errors['base'] = 'invalid_login'

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str
            }),
            errors=errors
        )

    async def async_step_2fa(self, user_input=None):
        """Handle the 2fa step, if needed."""
        errors = {}

        if user_input is not None:
            from hangups import get_auth
            from .hangups_utils import GoogleAuthError
            self._credentials.set_verification_code(user_input[CONF_2FA])
            try:
                await self.hass.async_add_executor_job(get_auth,
                                                       self._credentials,
                                                       self._refresh_token)

                return await self.async_step_final()
            except GoogleAuthError:
                errors['base'] = 'invalid_2fa'

        return self.async_show_form(
            step_id=CONF_2FA,
            data_schema=vol.Schema({
                vol.Required(CONF_2FA): str,
            }),
            errors=errors
        )

    async def async_step_final(self):
        """Handle the final step, create the config entry."""
        return self.async_create_entry(
            title=self._credentials.get_email(),
            data={
                CONF_EMAIL: self._credentials.get_email(),
                CONF_REFRESH_TOKEN: self._refresh_token.get()
            })

    async def async_step_import(self, _):
        """Handle a flow import."""
        return await self.async_step_user()
