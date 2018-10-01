"""
Support for devices connected to Unifi POE.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/unifi/
"""

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN, CONF_SITE_ID
from .controller import UniFiController, get_controller
from .errors import AuthenticationRequired, CannotConnect, UserLevel

DEFAULT_PORT = 8443
DEFAULT_SITE_ID = 'default'
DEFAULT_VERIFY_SSL = False

REQUIREMENTS = ['aiounifi==1']


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the UniFi component."""
    controller = UniFiController(hass, config_entry)

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][controller.host] = controller

    if not await controller.async_setup():
        return False

    if controller.mac is None:
        return True

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, controller.mac)},
        # identifiers={
        #     (DOMAIN, config.bridgeid)
        # },
        manufacturer='Ubiquity',
        # name=config.name,
        # model=config.raw['modelid'],
        # sw_version=config.raw['swversion'],
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    controller = hass.data[DOMAIN].pop(config_entry.data['host'])
    return await controller.async_reset()


@config_entries.HANDLERS.register(DOMAIN)
class UnifiFlowHandler(data_entry_flow.FlowHandler):
    """Handle a UniFi config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the UniFi flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            try:
                data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
                    CONF_SITE_ID: user_input.get(
                        CONF_SITE_ID, DEFAULT_SITE_ID),
                    CONF_VERIFY_SSL: user_input.get(
                        CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                }
                controller = await get_controller(self.hass, **data)

                sites = await controller.sites()
                name = data[CONF_SITE_ID]
                for site in sites.values():
                    if data[CONF_SITE_ID] == site['name']:
                        if site['role'] != 'admin':
                            raise UserLevel
                        name = site['desc']
                        break

                return self.async_create_entry(
                    title=name,
                    data=data
                )

            except AuthenticationRequired:
                errors['base'] = 'faulty_credentials'

            except CannotConnect:
                errors['base'] = 'service_unavailable'

            except UserLevel:
                errors['base'] = 'user_privilege'

            except Exception as err:
                return self.async_abort(reason='unknown')

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_PORT): int,
                vol.Optional(CONF_SITE_ID): str,
                vol.Optional(CONF_VERIFY_SSL): bool,
            }),
            errors=errors,
        )
