"""Config flow for the Abode Security System component."""
from abodepy import Abode
from abodepy.exceptions import AbodeAuthenticationException, AbodeException
from abodepy.helpers.errors import MFA_CODE_REQUIRED
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, HTTP_BAD_REQUEST

from .const import DEFAULT_CACHEDB, DOMAIN, LOGGER  # pylint: disable=unused-import

CONF_MFA = "mfa_code"
CONF_POLLING = "polling"


class AbodeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Abode."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

        self.mfa_data_schema = {
            vol.Required(CONF_MFA): str,
        }

        self._username = None
        self._password = None
        self._polling = None
        self._cache = None

    async def _async_abode_login(self, step_id):
        """Handle login with Abode."""
        self._cache = self.hass.config.path(DEFAULT_CACHEDB)
        errors = {}

        try:
            await self.hass.async_add_executor_job(
                Abode, self._username, self._password, True, False, False, self._cache
            )

        except (AbodeException, ConnectTimeout, HTTPError) as ex:
            if ex.errcode == MFA_CODE_REQUIRED[0]:
                return await self.async_step_mfa()

            LOGGER.error("Unable to connect to Abode: %s", ex)

            if ex.errcode == HTTP_BAD_REQUEST:
                errors = {"base": "invalid_auth"}
            else:
                errors = {"base": "cannot_connect"}

        if errors:
            return self.async_show_form(
                step_id=step_id, data_schema=vol.Schema(self.data_schema), errors=errors
            )

        return await self._async_create_entry(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_POLLING: self._polling,
            }
        )

    async def _async_create_entry(self, user_input):
        """Create the config entry."""
        existing_entry = await self.async_set_unique_id(self._username)

        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            # Force reload the Abode config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title=self._username, data=user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(self.data_schema)
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._polling = user_input.get(CONF_POLLING, False)

        return await self._async_abode_login(step_id="user")

    async def async_step_mfa(self, user_input=None):
        """Handle multi-factor authentication (MFA) with Abode."""
        if user_input is None:
            return self.async_show_form(
                step_id="mfa", data_schema=vol.Schema(self.mfa_data_schema)
            )

        errors = {}
        mfa_code = user_input[CONF_MFA]

        try:
            # Create instance to access login method for passing MFA code
            abode = Abode(
                auto_login=False,
                get_devices=False,
                get_automations=False,
                cache_path=self._cache,
            )
            await self.hass.async_add_executor_job(
                abode.login, self._username, self._password, mfa_code
            )

        except AbodeAuthenticationException as ex:
            LOGGER.error("Invalid MFA code: %s", ex)
            errors = {"base": "invalid_mfa_code"}

        if errors:
            return self.async_show_form(
                step_id="mfa",
                data_schema=vol.Schema(self.mfa_data_schema),
                errors=errors,
            )

        return await self._async_create_entry(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_POLLING: self._polling,
            }
        )

    async def async_step_reauth(self, config):
        """Handle reauthorization request from Abode."""
        self._username = config[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauthorization flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME, default=self._username): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_abode_login(step_id="reauth_confirm")

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            LOGGER.warning("Only one configuration of abode is allowed.")
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)
