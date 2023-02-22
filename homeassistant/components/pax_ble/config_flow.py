"""Config flow to configure Pax integration"""

import logging

import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
import voluptuous as vol
from homeassistant import config_entries
from datetime import timedelta

from .const import DOMAIN, CONF_NAME, CONF_MAC, CONF_PIN, CONF_SCAN_INTERVAL
from .const import DEFAULT_SCAN_INTERVAL

from .calima import Calima

_LOGGER = logging.getLogger(__name__)

class PaxConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        # Context stores the data used for the flows
        context = {}

    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PaxOptionsFlowHandler(config_entry) 

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self.setContext("", "", "", DEFAULT_SCAN_INTERVAL)
        
        return await self.async_step_add_device()

    async def async_step_bluetooth(self, discovery_info):
        """Handle a flow initialized by bluetooth discovery."""
        await self.async_set_unique_id(dr.format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.setContext(discovery_info.name, dr.format_mac(discovery_info.address), "", DEFAULT_SCAN_INTERVAL)

        return await self.async_step_add_device()

    """##################################################
    ##################### ADD DEVICE ####################
    ##################################################"""
    async def async_step_add_device(self, user_input=None):       
        """ Common handler for adding device. """
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(dr.format_mac(user_input[CONF_MAC]))
            self._abort_if_unique_id_configured()

            fan = Calima(self.hass, user_input[CONF_MAC], user_input[CONF_PIN])
            await fan.connect()
            
            if fan.isConnected():
                await fan.disconnect()
                return self.async_create_entry(title=user_input[CONF_NAME],data=user_input)
            else:
                errors["base"] = "cannot_connect"

                # Store values for new attempt
                self.context = user_input

        data_schema = getDeviceSchema(self.context)
        return self.async_show_form(step_id="add_device", data_schema=data_schema, errors=errors)

    def setContext(self, name, mac, pin, scan_interval):
        self.context[CONF_NAME] = name
        self.context[CONF_MAC] = mac
        self.context[CONF_PIN] = pin
        self.context[CONF_SCAN_INTERVAL] = scan_interval

class PaxOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        # Manage the options for the custom component."""
        return await self.async_step_configure_device()

    """##################################################
    ################## CONFIGURE DEVICE #################
    ##################################################"""
    async def async_step_configure_device(self, user_input=None):
        """ Common handler for configuring device. """
        errors = {}

        if user_input is not None:
            # Add data from original config entry
            user_input[CONF_NAME] = self.config_entry.data[CONF_NAME]
            user_input[CONF_MAC] = self.config_entry.data[CONF_MAC]
        
            # Update config entry
            self.hass.config_entries.async_update_entry(self.config_entry, data=user_input, options=self.config_entry.options)            

            # Store no options - we have updated config entry
            return self.async_create_entry(title="", data={})

        data_schema = getDeviceSchemaOptions(self.config_entry.data)
        return self.async_show_form(step_id="configure_device", data_schema=data_schema, errors=errors)

""" Schema Helper functions """
def getDeviceSchema(user_input):
    data_schema = vol.Schema(
        {
            vol.Required(CONF_NAME, description="Name", default=user_input[CONF_NAME]): cv.string,
            vol.Required(CONF_MAC, description="MAC Address", default=user_input[CONF_MAC]): cv.string,
            vol.Required(CONF_PIN, description="Pin Code", default=user_input[CONF_PIN]): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]): vol.All(vol.Coerce(int), vol.Range(min=1, max=999)),
        }
    )

    return data_schema

def getDeviceSchemaOptions(user_input):
    data_schema = vol.Schema(
        {
            vol.Required(CONF_PIN, description="Pin Code", default=user_input[CONF_PIN]): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]): vol.All(vol.Coerce(int), vol.Range(min=1, max=999))
        }
    )

    return data_schema
