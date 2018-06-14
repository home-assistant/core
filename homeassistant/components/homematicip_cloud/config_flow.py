"""Config flow to configure HomematicIP Cloud."""
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    DOMAIN, _LOGGER, CONF_ACCESSPOINT, CONF_AUTHTOKEN, CONF_PIN, CONF_NAME)


@callback
def configured_accesspoint(hass):
    """Return a set of the configured hosts."""
    return set(entry.data[CONF_ACCESSPOINT] for entry
               in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class HomematicipCloudFlowHandler(data_entry_flow.FlowHandler):
    """Config flow HomematicIP Cloud."""

    VERSION = 1

    def __init__(self):
        """Initialize HomematicIP Cloud config flow."""
        self.hmip_auth = None
        self.hmip_apid = None
        self.hmip_name = ''

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        from homematicip.aio.auth import AsyncAuth
        from homematicip.base.base_connection import HmipConnectionError
        errors = {}

        if user_input is not None:
            self.hmip_apid = user_input[CONF_ACCESSPOINT]

            if self.hmip_apid in configured_accesspoint(self.hass):
                return self.async_abort(reason='already_configured')
            if user_input[CONF_NAME] is not None:
                self.hmip_name = user_input[CONF_NAME]
            _LOGGER.info("Create new authtoken for %s", self.hmip_apid)

            # Create new authtoken for the accesspoint
            websession = aiohttp_client.async_get_clientsession(self.hass)
            self.hmip_auth = AsyncAuth(self.hass.loop, websession)
            try:
                await self.hmip_auth.init(self.hmip_apid)
            except HmipConnectionError:
                return self.async_abort(reason='conection_aborted')
            if user_input[CONF_PIN]:
                self.hmip_auth.pin = user_input[CONF_PIN]
            try:
                await self.hmip_auth.connectionRequest(
                    'HomeAssistant')
            except HmipConnectionError:
                errors['base'] = 'register_failed'
            else:
                # Connection established
                _LOGGER.info("Connection established")
                return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_ACCESSPOINT): str,
                vol.Optional(CONF_PIN): str,
                vol.Optional(CONF_NAME): str,
            }),
            errors=errors
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the HomematicIP Cloud accesspoint."""
        from homematicip.base.base_connection import HmipConnectionError
        errors = {}

        try:
            await self.hmip_auth.isRequestAcknowledged()
        except HmipConnectionError:
            errors['base'] = 'press_the_button'
        else:
            try:
                authtoken = await self.hmip_auth.requestAuthToken()
                await self.hmip_auth.confirmAuthToken(authtoken)
            except HmipConnectionError:
                return self.async_abort(reason='conection_aborted')
            else:
                _LOGGER.info("Register new config entry")
                apid = self.hmip_apid.replace('-', '').upper()
                return self.async_create_entry(
                    title=apid,
                    data={
                        'accesspoint': apid,
                        'authtoken': authtoken,
                        'name': self.hmip_name
                        }
                )

        return self.async_show_form(step_id='link', errors=errors)

    async def async_step_import(self, import_info):
        """Import a new bridge as a config entry."""
        apid = import_info[CONF_ACCESSPOINT]
        authtoken = import_info[CONF_AUTHTOKEN]
        name = import_info[CONF_NAME]

        apid = apid.replace('-', '').upper()
        if apid in configured_accesspoint(self.hass):
            return self.async_abort(reason='already_configured')

        _LOGGER.info('Imported authentication for %s', apid)

        return self.async_create_entry(
            title=apid,
            data={
                'accesspoint': apid,
                'authtoken': authtoken,
                'name': name
                }
        )
