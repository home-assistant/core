"""Config flow to configure HomematicIP Cloud."""
import asyncio

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow

from .const import (
    DOMAIN, _LOGGER,
    CONF_ACCESSPOINT, CONF_AUTHTOKEN, CONF_NAME, CONF_PIN)


@config_entries.HANDLERS.register(DOMAIN)
class HomematicipCloudFlowHandler(data_entry_flow.FlowHandler):
    """Config flow HomematicIP Cloud."""

    VERSION = 1

    def __init__(self):
        """Initialize HomematicIP Cloud configuration flow."""
        _LOGGER.error("config_flow init")

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        _LOGGER.error("config_flow step_init")
        errors = {}

        if user_input is not None:
            _LOGGER.error("config_flow step_init")
            if user_input[CONF_ACCESSPOINT]:
                apid = user_input[CONF_ACCESSPOINT].replace('-', '').upper()
                if user_input[CONF_AUTHTOKEN]:
                    # Add existing accespoint with SGTIN and auth token
                    return self.async_create_entry(
                        title=apid,
                        data={
                            'name': user_input[CONF_NAME],
                            'accesspoint': apid,
                            'authtoken': user_input[CONF_AUTHTOKEN],
                        }
                    )
                # Init home and go to step link
                # TO BE IMPLEMENTED
                return await self.async_step_link()
            return

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_ACCESSPOINT): str,
                vol.Optional(CONF_PIN): str,
                vol.Optional(CONF_NAME): str,
                vol.Optional(CONF_AUTHTOKEN): str,
            }),
            errors=errors,
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the HomematicIP Cloud accesspoint."""
        errors = {}
        _LOGGER.error("config_flow step_link")

        return self.async_show_form(step_id='link', errors=errors)

    async def _entry_from_accesspoint(self, home):
        """Return a config entry from an initialized homematicip instance."""
        return self.async_create_entry(
            title=home.id.replace('-', '').upper(),
            data={
                'name': home.label,
                'accesspoint': home.id.replace('-', '').upper(),
                # pylint: disable=protected-access
                'authtoken': home._connection._auth_token,
            }
        )
