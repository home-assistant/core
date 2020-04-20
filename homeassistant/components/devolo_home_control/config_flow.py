"""Config flow to configure the devolo home control integration."""
import logging

from devolo_home_control_api.mydevolo import Mydevolo, WrongCredentialsError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class DevoloHomeControlFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a devolo HomeControl config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize devolo Home Control flow."""
        self.data_schema = {
            vol.Required(CONF_USERNAME, default=""): str,
            vol.Required(CONF_PASSWORD): str,
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        try:
            if user_input is None:
                return self._show_form(user_input)
            user = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            mydevolo = Mydevolo.get_instance()
            mydevolo.user = user
            mydevolo.password = password
            credentials_valid = await self.hass.async_add_executor_job(
                mydevolo.credentials_valid
            )
            if credentials_valid:
                _LOGGER.debug("Credentials valid")
                return self.async_create_entry(
                    title="devolo Home Control",
                    data={CONF_PASSWORD: password, CONF_USERNAME: user},
                )
        except WrongCredentialsError:
            return self._show_form({"base": "invalid_credentials"})

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )


def create_config_flow(hass):
    """Start a config flow."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )
    )
