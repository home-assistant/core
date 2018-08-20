"""Config flow to configure HomematicIP Cloud."""
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import callback

from .const import (
    DOMAIN as HMIPC_DOMAIN, _LOGGER,
    HMIPC_HAPID, HMIPC_AUTHTOKEN, HMIPC_PIN, HMIPC_NAME)
from .hap import HomematicipAuth


@callback
def configured_haps(hass):
    """Return a set of the configured accesspoints."""
    return set(entry.data[HMIPC_HAPID] for entry
               in hass.config_entries.async_entries(HMIPC_DOMAIN))


@config_entries.HANDLERS.register(HMIPC_DOMAIN)
class HomematicipCloudFlowHandler(data_entry_flow.FlowHandler):
    """Config flow HomematicIP Cloud."""

    VERSION = 1

    def __init__(self):
        """Initialize HomematicIP Cloud config flow."""
        self.auth = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            user_input[HMIPC_HAPID] = \
                user_input[HMIPC_HAPID].replace('-', '').upper()
            if user_input[HMIPC_HAPID] in configured_haps(self.hass):
                return self.async_abort(reason='already_configured')

            self.auth = HomematicipAuth(self.hass, user_input)
            connected = await self.auth.async_setup()
            if connected:
                _LOGGER.info("Connection established")
                return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(HMIPC_HAPID): str,
                vol.Optional(HMIPC_PIN): str,
                vol.Optional(HMIPC_NAME): str,
            }),
            errors=errors
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the HomematicIP Cloud accesspoint."""
        errors = {}

        pressed = await self.auth.async_checkbutton()
        if pressed:
            authtoken = await self.auth.async_register()
            if authtoken:
                _LOGGER.info("Write config entry")
                return self.async_create_entry(
                    title=self.auth.config.get(HMIPC_HAPID),
                    data={
                        HMIPC_HAPID: self.auth.config.get(HMIPC_HAPID),
                        HMIPC_AUTHTOKEN: authtoken,
                        HMIPC_NAME: self.auth.config.get(HMIPC_NAME)
                    })
            return self.async_abort(reason='conection_aborted')
        errors['base'] = 'press_the_button'

        return self.async_show_form(step_id='link', errors=errors)

    async def async_step_import(self, import_info):
        """Import a new bridge as a config entry."""
        hapid = import_info[HMIPC_HAPID]
        authtoken = import_info[HMIPC_AUTHTOKEN]
        name = import_info[HMIPC_NAME]

        hapid = hapid.replace('-', '').upper()
        if hapid in configured_haps(self.hass):
            return self.async_abort(reason='already_configured')

        _LOGGER.info('Imported authentication for %s', hapid)

        return self.async_create_entry(
            title=hapid,
            data={
                HMIPC_HAPID: hapid,
                HMIPC_AUTHTOKEN: authtoken,
                HMIPC_NAME: name
            }
        )
