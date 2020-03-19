"""Config flow to configure the devolo home control integration."""
import logging

from devolo_home_control_api.mydevolo import Mydevolo, WrongCredentialsError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _login_data_valid(user, password):
    """Validate the given login data.

    Raise WrongCredentialsError if data is wrong.
    """
    mydevolo = Mydevolo.get_instance()
    mydevolo.user = user
    mydevolo.password = password
    mydevolo.uuid


@config_entries.HANDLERS.register(DOMAIN)
class DevoloHomeControlFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a devolo HomeControl config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize devolo Home Control flow."""
        self.data_schema = {
            vol.Required(CONF_USERNAME, default=""): str,
            vol.Required(CONF_PASSWORD): str,
        }

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        try:
            if user_input is None:
                return await self._show_setup_form(user_input)
            user = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)
            _login_data_valid(user=user, password=password)
            _LOGGER.debug("Credentials valid")
            return self.async_create_entry(
                title="devolo Home Control",
                data={
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                    CONF_USERNAME: user_input.get(CONF_USERNAME),
                },
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
