"""Config flow to configure IPMA component."""
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

from .const import DOMAIN, HOME_LOCATION_NAME


@config_entries.HANDLERS.register(DOMAIN)
class IpmaFlowHandler(data_entry_flow.FlowHandler):
    """Config flow for SMHI component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            valid = await self._check_location(
                user_input[CONF_LONGITUDE], user_input[CONF_LATITUDE])
            if valid:
                if user_input[CONF_NAME] not in hass.config_entries.async_entries(DOMAIN)
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input,
                    )

                self._errors[CONF_NAME] = 'name_exists'
            else:
                self._errors['base'] = 'wrong_location'

        # If hass config has the location set and is a valid coordinate the
        # default location is set as default values in the form
        if await self._check_location(self.hass.config.latitude,
            self.hass.config.longitude):
            return await self._show_config_form(
                name=HOME_LOCATION_NAME,
                latitude=self.hass.config.latitude,
                longitude=self.hass.config.longitude
            )

        return await self._show_config_form()

    async def _show_config_form(self, name = None, latitude = None,
                                longitude: str = None):
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

    async def _check_location(self, latitude, longitude):
        """Return true if location is ok."""
        try:
            if -180 <= float(longitude) <= 180 and
                90 <= float(latitude) <= 90:
                return True
        except ValueError:
            #not a valie geo coordinate
            pass

        return False

