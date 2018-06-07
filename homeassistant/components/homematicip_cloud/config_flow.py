"""Config flow to configure HomematicIP Cloud."""
import json

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow

from .const import DOMAIN, _LOGGER, CONF_ACCESSPOINT, CONF_PIN, CONF_NAME


@config_entries.HANDLERS.register(DOMAIN)
class HomematicipCloudFlowHandler(data_entry_flow.FlowHandler):
    """Config flow HomematicIP Cloud."""

    VERSION = 1

    def __init__(self):
        """Initialize HomematicIP Cloud config flow."""
        self.hmip_auth = None
        self.hmip_apid = None
        self.hmip_name = None

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        from homematicip.home import Home
        from homematicip.auth import Auth

        errors = {}

        if user_input is not None:
            if user_input[CONF_ACCESSPOINT]:
                self.hmip_apid = user_input[CONF_ACCESSPOINT]
                self.hmip_name = user_input[CONF_NAME]
                _LOGGER.info("Create new authtoken for %s", self.hmip_apid)

                # Create new authtoken for the accesspoint
                # Threaded version needs to be migrated to async
                home = Home()
                home.init(self.hmip_apid)
                self.hmip_auth = Auth(home)
                if user_input[CONF_PIN]:
                    self.hmip_auth.pin = user_input[CONF_PIN]
                res = self.hmip_auth.connectionRequest(self.hmip_apid,
                                                       'HomeAssistant')

                # Connection established
                if res.status_code == 200:
                    _LOGGER.info("Connection established")
                    return await self.async_step_link()

                error_code = json.loads(res.text)['errorCode']
                if error_code == 'INVALID_PIN':
                    errors['base'] = 'invalid_pin'
                else:
                    errors['base'] = 'register_failed'

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
        errors = {}
        _LOGGER.info("Wait for hardware button acknowledg")

        # Wait for blue button pressed
        if self.hmip_auth.isRequestAcknowledged():
            authtoken = self.hmip_auth.requestAuthToken()
            self.hmip_auth.confirmAuthToken(authtoken)

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
