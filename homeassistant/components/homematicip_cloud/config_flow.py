"""Config flow to configure HomematicIP Cloud."""
import asyncio

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, _LOGGER, CONF_ACCESSPOINT, CONF_PIN, CONF_NAME


@config_entries.HANDLERS.register(DOMAIN)
class HomematicipCloudFlowHandler(data_entry_flow.FlowHandler):
    """Config flow HomematicIP Cloud."""

    VERSION = 1

    def __init__(self):
        """Initialize HomematicIP Cloud config flow."""
        self.first_link = True
        self.hmip_auth = None
        self.hmip_apid = None
        self.hmip_name = None

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        from homematicip.aio.auth import AsyncAuth
        from homematicip.base.base_connection import HmipConnectionError
        errors = {}

        if user_input is not None:
            if user_input[CONF_ACCESSPOINT]:
                self.hmip_apid = user_input[CONF_ACCESSPOINT]
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
                    state = await self.hmip_auth.connectionRequest(
                        'HomeAssistant')
                except HmipConnectionError:
                    if state['errorCode'] == 'INVALID_PIN':
                        errors[CONF_PIN] = 'invalid_pin'
                    else:
                        errors['base'] = 'register_failed'
                else:
                    # Connection established
                    _LOGGER.info("Connection established")
                    self.first_link = True
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

        if self.first_link:
            self.first_link = False
            return self.async_show_form(step_id='link', errors=errors)

        _LOGGER.info("Wait for hardware button acknowledg")
        # Wait for blue button pressed
        wait = 30
        state = False
        while (not state or wait >= 0):
            try:
                state = await self.hmip_auth.isRequestAcknowledged()
            except HmipConnectionError:
                wait = wait - 1
            await asyncio.sleep(1)
        if wait == 0:
            errors['base'] = 'timeout_button'

        if state:
            try:
                authtoken = await self.hmip_auth.requestAuthToken()
                await self.hmip_auth.confirmAuthToken(authtoken)
            except HmipConnectionError:
                return self.async_abort(reason='conection_aborted')
            else:
                _LOGGER.info("Register new config entry")
                return self.async_create_entry(
                    title=self.hmip_apid,
                    data={
                        'accesspoint': self.hmip_apid.replace('-', '').upper(),
                        'authtoken': authtoken,
                        'name': self.hmip_name
                        }
                )

        return self.async_show_form(step_id='link', errors=errors)
