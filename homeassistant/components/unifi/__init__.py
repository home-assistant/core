""""""

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME)

from .const import DOMAIN, LOGGER, CONF_SITE_ID
from .controller import UniFiController, get_controller
from .errors import AuthenticationRequired, CannotConnect

DOMAIN = 'unifi'

CONF_SITE_ID = 'site'

#REQUIREMENTS = ['aiounifi==1']


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    return True


async def async_setup_entry(hass, config_entry):
    """"""
    controller = UniFiController(hass, config_entry)

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][controller.host] = controller

    if not await controller.async_setup():
        return False

    # config = controller.api.config
    # device_registry = await \
    #     hass.helpers.device_registry.async_get_registry()
    # device_registry.async_get_or_create(
    #     config_entry=config_entry.entry_id,
    #     connections={
    #         (device_registry.CONNECTION_NETWORK_MAC, config.mac)
    #     },
    #     identifiers={
    #         (DOMAIN, config.bridgeid)
    #     },
    #     manufacturer='Signify',
    #     name=config.name,
    #     # Not yet exposed as properties in aiohue
    #     model=config.raw['modelid'],
    #     sw_version=config.raw['swversion'],
    # )

    return True


async def async_unload_entry(hass, config_entry):
    """"""
    print('Unifi unload entry')
    return True


@config_entries.HANDLERS.register(DOMAIN)
class UnifiFlowHandler(data_entry_flow.FlowHandler):
    """Handle a UniFi config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the UniFi flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        if user_input is not None:
            print(user_input)
            try:
                controller = await get_controller(self.hass, **user_input)

                return self.async_create_entry(
                    title='Unifi *site id*',
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_PORT: user_input.get(CONF_PORT, 8443),
                        CONF_SITE_ID: user_input.get(CONF_SITE_ID, 'default'),
                    }
                )
            except Exception as err:
                print('exception', err)

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_PORT): int,
                vol.Optional(CONF_SITE_ID): str,
            })
        )
