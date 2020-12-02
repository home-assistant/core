"""Config flow to configure the devolo home control integration."""
import logging

from devolo_home_control_api.mydevolo import Mydevolo
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_MYDEVOLO, DEFAULT_MYDEVOLO, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DevoloHomeControlFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a devolo HomeControl config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize devolo Home Control flow."""
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self.show_advanced_options:
            self.data_schema = {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_MYDEVOLO, default=DEFAULT_MYDEVOLO): str,
            }
        if user_input is None:
            return self._show_form(user_input)
        return await self._helper(user_input)

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Handle zeroconf discovery."""
        try:
            # Check if it is a gateway
            if discovery_info["hostname"].startswith("devolo-homecontrol"):
                # Check if already configured
                try:
                    for entry in self.hass.data[DOMAIN].values():
                        for gw in entry["gateways"]:
                            if gw.gateway.id == discovery_info["properties"]["SN"]:
                                return self.async_abort(
                                    reason="Gateway already configured"
                                )
                    return await self.async_step_zeroconf_confirm()
                except KeyError:
                    self.async_abort(reason="devolo home control not yet configured.")
                return await self.async_step_zeroconf_confirm()
            else:
                return self.async_abort(reason="Not a devolo homecontrol gateway.")
        except KeyError:
            return self.async_abort(reason="Not a devolo homecontrol gateway.")

    async def async_step_zeroconf_confirm(self, user_input=None):
        """Handle a flow initiated by zeroconf."""
        if user_input is None:
            return self._show_form(step_id="zeroconf_confirm")
        return await self._helper(user_input)

    async def _helper(self, user_input):
        # TODO: Find a better function name
        user = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        mydevolo = Mydevolo()
        mydevolo.user = user
        mydevolo.password = password
        if self.show_advanced_options:
            mydevolo.url = user_input[CONF_MYDEVOLO]
        else:
            mydevolo.url = DEFAULT_MYDEVOLO
        credentials_valid = await self.hass.async_add_executor_job(
            mydevolo.credentials_valid
        )
        if not credentials_valid:
            return self._show_form({"base": "invalid_auth"})
        _LOGGER.debug("Credentials valid")
        uuid = await self.hass.async_add_executor_job(mydevolo.uuid)
        await self.async_set_unique_id(uuid)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="devolo Home Control",
            data={
                CONF_PASSWORD: password,
                CONF_USERNAME: user,
                CONF_MYDEVOLO: mydevolo.url,
            },
        )

    @callback
    def _show_form(self, errors=None, step_id="user"):
        """Show the form to the user."""
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )
