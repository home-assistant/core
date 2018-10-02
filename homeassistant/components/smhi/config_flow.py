"""Config flow to configure smhi component.

First time the user creates the configuration and
a location is set in the hass configuration yaml it
will use that location and create a default
home location. This behavior will change when
configuration flow supports default values.

When home location exists a form will show
to add additional locations for weather data.

The input location will be checked by invoking
the API. Exception will be thrown if the location
is not supported by the API (Swedish location only)
"""
from typing import Dict

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.util import slugify

from .const import DOMAIN, HOME_LOCATION_NAME

REQUIREMENTS = ['smhi-pkg==1.0.3']


@callback
def smhi_locations(hass: HomeAssistant):
    """Return configurations of smhi component."""
    return set((slugify(entry.data[CONF_NAME])) for
               entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class SmhiFlowHandler(data_entry_flow.FlowHandler):
    """Smhi config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize smhi forecast configuration flow."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle the flow logic for SMHI location config."""
        self._errors = {}

        # If hass config has the location set and
        # is a valid coordinate andit is not configured
        # already, the defaultlocation is created at
        # home coordinates
        if not self._home_location_exists() and \
           await self._homeassistant_location_exists():
            return await self._create_home_location_entry()

        # Add the location if not already exists
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

    def _home_location_exists(self) -> bool:
        """Return True if home location exists."""
        if slugify(HOME_LOCATION_NAME) in smhi_locations(self.hass):
            return True
        return False

    def _name_in_configuration_exists(self, name: str) -> bool:
        """Return True if name exists in configuration."""
        if name in smhi_locations(self.hass):
            return True
        return False

    async def _create_home_location_entry(self) -> Dict:
        """Create default home location entry."""
        return self.async_create_entry(
            title=HOME_LOCATION_NAME,
            data={
                CONF_NAME: HOME_LOCATION_NAME,
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude
            })

    async def _show_config_form(self):
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_LATITUDE): cv.latitude,
                vol.Required(CONF_LONGITUDE): cv.longitude
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
