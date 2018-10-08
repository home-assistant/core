"""Config flow to configure smhi component.

First time the user creates the configuration and
a valid location is set in the hass configuration yaml
it will use that location and use it as default values.

Additional locations can be added in config form.
The input location will be checked by invoking
the API. Exception will be thrown if the location
is not supported by the API (Swedish locations only)
"""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.util import slugify

from .const import DOMAIN, HOME_LOCATION_NAME

REQUIREMENTS = ['smhi-pkg==1.0.4']


@callback
def smhi_locations(hass: HomeAssistant):
    """Return configurations of SMHI component."""
    return set((slugify(entry.data[CONF_NAME])) for
               entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class SmhiFlowHandler(data_entry_flow.FlowHandler):
    """Config flow for SMHI component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize SMHI forecast configuration flow."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            is_ok = await self._check_location(
                user_input[CONF_LONGITUDE],
                user_input[CONF_LATITUDE]
            )
            if is_ok:
                name = slugify(user_input[CONF_NAME])
                if not self._name_in_configuration_exists(name):
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input,
                    )

                self._errors[CONF_NAME] = 'name_exists'
            else:
                self._errors['base'] = 'wrong_location'

        # If hass config has the location set and
        # is a valid coordinate the default location
        # is set as default values in the form
        if not smhi_locations(self.hass):
            if await self._homeassistant_location_exists():
                return await self._show_config_form(
                    name=HOME_LOCATION_NAME,
                    latitude=self.hass.config.latitude,
                    longitude=self.hass.config.longitude
                )

        return await self._show_config_form()

    async def _homeassistant_location_exists(self) -> bool:
        """Return true if default location is set and is valid."""
        if self.hass.config.latitude != 0.0 and \
           self.hass.config.longitude != 0.0:
            # Return true if valid location
            if await self._check_location(
                    self.hass.config.longitude,
                    self.hass.config.latitude):
                return True
        return False

    def _name_in_configuration_exists(self, name: str) -> bool:
        """Return True if name exists in configuration."""
        if name in smhi_locations(self.hass):
            return True
        return False

    async def _show_config_form(self,
                                name: str = None,
                                latitude: str = None,
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

    async def _check_location(self, longitude: str, latitude: str) -> bool:
        """Return true if location is ok."""
        from smhi.smhi_lib import Smhi, SmhiForecastException
        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            smhi_api = Smhi(longitude, latitude, session=session)

            await smhi_api.async_get_forecast()

            return True
        except SmhiForecastException:
            # The API will throw an exception if faulty location
            pass

        return False
