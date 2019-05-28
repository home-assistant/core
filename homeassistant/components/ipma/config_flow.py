"""Config flow to configure IPMA component."""
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, HOME_LOCATION_NAME


@config_entries.HANDLERS.register(DOMAIN)
class IpmaFlowHandler(data_entry_flow.FlowHandler):
    """Config flow for IPMA component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Init IpmaFlowHandler."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            if user_input[CONF_NAME] not in\
                    self.hass.config_entries.async_entries(DOMAIN):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

            self._errors[CONF_NAME] = 'name_exists'

        # default location is set hass configuration
        return await self._show_config_form(
            name=HOME_LOCATION_NAME,
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude)

    async def _show_config_form(self, name=None, latitude=None,
                                longitude=None):
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=name): str,
                vol.Required(CONF_LATITUDE, default=latitude): cv.latitude,
                vol.Required(CONF_LONGITUDE, default=longitude): cv.longitude
            }),
            errors=self._errors,
        )
