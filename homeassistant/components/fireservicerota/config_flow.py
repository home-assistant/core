"""Config flow for FireServiceRota."""
from pyfireservicerota import FireServiceRota, InvalidAuthError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_URL, CONF_USERNAME

from .const import DOMAIN, URL_LIST

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="www.brandweerrooster.nl"): vol.In(URL_LIST),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class FireServiceRotaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a FireServiceRota config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self.api = None
        self._base_url = None
        self._username = None
        self._password = None
        self._existing_entry = None
        self._description_placeholders = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        return await self._validate_and_create_entry(user_input, "user")

    async def _validate_and_create_entry(self, user_input, step_id):
        """Check if config is valid and create entry if so."""
        self._password = user_input[CONF_PASSWORD]

        extra_inputs = user_input

        if self._existing_entry:
            extra_inputs = self._existing_entry

        self._username = extra_inputs[CONF_USERNAME]
        self._base_url = extra_inputs[CONF_URL]

        if self.unique_id is None:
            await self.async_set_unique_id(self._username)
            self._abort_if_unique_id_configured()

        self.api = FireServiceRota(
            base_url=self._base_url,
            username=self._username,
            password=self._password,
        )

        try:
            token_info = await self.hass.async_add_executor_job(self.api.request_tokens)
        except InvalidAuthError:
            self.api = None
            return self.async_show_form(
                step_id=step_id,
                data_schema=DATA_SCHEMA,
                errors={"base": "invalid_auth"},
            )

        data = {
            "auth_implementation": DOMAIN,
            CONF_URL: self._base_url,
            CONF_USERNAME: self._username,
            CONF_TOKEN: token_info,
        }

        if step_id == "user":
            return self.async_create_entry(title=self._username, data=data)

        entry = await self.async_set_unique_id(self.unique_id)
        self.hass.config_entries.async_update_entry(entry, data=data)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    def _show_setup_form(self, user_input=None, errors=None, step_id="user"):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        if step_id == "user":
            schema = {
                vol.Required(CONF_URL, default="www.brandweerrooster.nl"): vol.In(
                    URL_LIST
                ),
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        else:
            schema = {vol.Required(CONF_PASSWORD): str}

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(schema),
            errors=errors or {},
            description_placeholders=self._description_placeholders,
        )

    async def async_step_reauth(self, user_input=None):
        """Get new tokens for a config entry that can't authenticate."""

        if not self._existing_entry:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._existing_entry = user_input.copy()
            self._description_placeholders = {"username": user_input[CONF_USERNAME]}
            user_input = None

        if user_input is None:
            return self._show_setup_form(step_id=config_entries.SOURCE_REAUTH)

        return await self._validate_and_create_entry(
            user_input, config_entries.SOURCE_REAUTH
        )
