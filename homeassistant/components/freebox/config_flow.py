"""Config flow to configure the Freebox integration."""
import logging
import voluptuous as vol

from freebox_api.exceptions import AuthorizationError, HttpRequestError, InsufficientPermissionsError
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, CONF_WITH_HOME, PERMISSION_DEFAULT, PERMISSION_HOME
from .router import get_api, reset_api

_LOGGER = logging.getLogger(__name__)



class FreeboxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize Freebox config flow."""
        self._host = None
        self._port = None
        self._with_home = False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return FreeboxOptionsFlowHandler(config_entry)
        
    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=user_input.get(CONF_PORT, "")): int
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]

        # Check if already configured
        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured()

        return self.async_show_form(step_id="link")

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Freebox router.

        Given a configured host, will ask the user to press the button
        to connect to the router.
        """
        if user_input is None:
            return self.async_show_form(step_id="link")

        errors = {}
        if( await check_freebox_permission(self.hass, self._host, self._port, PERMISSION_DEFAULT, errors) ):
            data_schema=vol.Schema({vol.Required(CONF_WITH_HOME, default=self._with_home): bool})
            return self.async_show_form(step_id="option_home", data_schema=data_schema)

        return self.async_show_form(step_id="link", errors=errors)

    async def async_step_option_home(self, user_input=None):
        ''' Check if the user wants to use the Home API '''
        if user_input is None:
            return self.async_show_form(step_id="link")
            
        self._with_home = user_input[CONF_WITH_HOME]
        if( self._with_home == False):
            return self.async_create_entry(title=self._host,data={CONF_HOST: self._host, CONF_PORT: self._port, CONF_WITH_HOME: self._with_home})
        
        errors = {}
        if( await check_freebox_permission(self.hass, self._host, self._port, PERMISSION_HOME, errors) ):
            return self.async_create_entry(title=self._host,data={CONF_HOST: self._host, CONF_PORT: self._port, CONF_WITH_HOME: self._with_home})
        data_schema=vol.Schema({vol.Required(CONF_WITH_HOME, default=self._with_home): bool})
        return self.async_show_form(step_id="option_home", data_schema=data_schema, errors=errors)


    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(self, discovery_info: dict):
        """Initialize flow from zeroconf."""
        host = discovery_info["properties"]["api_domain"]
        port = discovery_info["properties"]["https_port"]
        return await self.async_step_user({CONF_HOST: host, CONF_PORT: port})



class FreeboxOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an option flow."""

    def __init__(self, entry: config_entries.ConfigEntry, domain=DOMAIN):
        """Initialize options flow."""
        self.entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._with_home = entry.options.get(CONF_WITH_HOME, entry.data.get(CONF_WITH_HOME, False))


    async def async_step_init(self, user_input=None):
        ''' Check if the user wants to use the Home API '''
        errors = {}

        if user_input is not None:
            self._with_home = user_input[CONF_WITH_HOME]
            if( self._with_home == False):
                return self.async_create_entry(title="", data=user_input)
            if( await check_freebox_permission(self.hass, self._host, self._port, PERMISSION_HOME, errors) ):
                return self.async_create_entry(title=self._host,data={CONF_WITH_HOME: self._with_home})
            data_schema = vol.Schema({vol.Required(CONF_WITH_HOME, default=self._with_home): bool})
            return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)

        data_schema = vol.Schema({vol.Required(CONF_WITH_HOME, default=self._with_home): bool})
        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)




async def check_freebox_permission(hass, host, port, check_type, errors = {},loop=True):
    fbx = await get_api(hass, host)
    try:
        await fbx.open(host, port)
        if( check_type == PERMISSION_DEFAULT ):
            await fbx.system.get_config()
            await fbx.lan.get_hosts_list()
            await hass.async_block_till_done()
        else:
            await fbx.home.get_home_nodes()
        await fbx.close()
        return True

    except AuthorizationError as error:
        # We must remove the existing config file and do a single connection retry
        # It's necessary when the user remive the application into the freebox UI => we must setup a new access 
        await reset_api(hass, host)
        if( loop == True):
            return await check_freebox_permission(hass, host, port, check_type, errors, False)
        _LOGGER.error(error)
        errors["base"] = "register_failed"

    except InsufficientPermissionsError as error:
        errors["base"] = "insufficient_permission"

    except HttpRequestError:
        _LOGGER.error("Error connecting to the Freebox router at %s", host)
        errors["base"] = "cannot_connect"

    except Exception as error:
        _LOGGER.exception("Unknown error connecting with Freebox router at %s. %s", host, error)
        errors["base"] = "unknown"

    await fbx.close()
    return False