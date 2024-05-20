"""Config flow to configure Dreo."""
import logging
import voluptuous as vol
from hscloud.hscloud import HsCloud
from collections import OrderedDict
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from .const import DOMAIN
import hashlib

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)


class DreoFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Dreo config flow."""

    def __init__(self) -> None:
        """Instantiate config flow."""
        self._username = None
        self._password = None
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str

    @callback
    def _show_form(self, errors=None):
        """Show form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not user_input:
            return self._show_form()

        self._username = user_input[CONF_USERNAME]
        self._password = hashlib.md5(user_input[CONF_PASSWORD].encode("UTF-8")).hexdigest()

        manager = HsCloud(self._username, self._password)
        login = await self.hass.async_add_executor_job(manager.login)
        if not login:
            return self._show_form(errors={"base": "invalid_auth"})

        return self.async_create_entry(
            title=self._username,
            data={CONF_USERNAME: self._username, CONF_PASSWORD: self._password},
        )