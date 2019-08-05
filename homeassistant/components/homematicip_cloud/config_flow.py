"""Config flow to configure the HomematicIP Cloud component."""
from typing import Set

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback

from .const import (
    _LOGGER, DOMAIN as HMIPC_DOMAIN, HMIPC_AUTHTOKEN, HMIPC_HAPID, HMIPC_NAME,
    HMIPC_PIN)
from .hap import HomematicipAuth


@callback
def configured_haps(hass: HomeAssistant) -> Set[str]:
    """Return a set of the configured access points."""
    return set(entry.data[HMIPC_HAPID] for entry
               in hass.config_entries.async_entries(HMIPC_DOMAIN))


@config_entries.HANDLERS.register(HMIPC_DOMAIN)
class HomematicipCloudFlowHandler(config_entries.ConfigFlow):
    """Config flow for the HomematicIP Cloud component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

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
                _LOGGER.info("Connection to HomematicIP Cloud established")
                return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(HMIPC_HAPID): str,
                vol.Optional(HMIPC_NAME): str,
                vol.Optional(HMIPC_PIN): str,
            }),
            errors=errors
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the HomematicIP Cloud access point."""
        errors = {}

        pressed = await self.auth.async_checkbutton()
        if pressed:
            authtoken = await self.auth.async_register()
            if authtoken:
                _LOGGER.info("Write config entry for HomematicIP Cloud")
                return self.async_create_entry(
                    title=self.auth.config.get(HMIPC_HAPID),
                    data={
                        HMIPC_HAPID: self.auth.config.get(HMIPC_HAPID),
                        HMIPC_AUTHTOKEN: authtoken,
                        HMIPC_NAME: self.auth.config.get(HMIPC_NAME)
                    })
            return self.async_abort(reason='connection_aborted')
        errors['base'] = 'press_the_button'

        return self.async_show_form(step_id='link', errors=errors)

    async def async_step_import(self, import_info):
        """Import a new access point as a config entry."""
        hapid = import_info[HMIPC_HAPID]
        authtoken = import_info[HMIPC_AUTHTOKEN]
        name = import_info[HMIPC_NAME]

        hapid = hapid.replace('-', '').upper()
        if hapid in configured_haps(self.hass):
            return self.async_abort(reason='already_configured')

        _LOGGER.info("Imported authentication for %s", hapid)

        return self.async_create_entry(
            title=hapid,
            data={
                HMIPC_AUTHTOKEN: authtoken,
                HMIPC_HAPID: hapid,
                HMIPC_NAME: name,
            }
        )
