"""Support for devices connected to UniFi POE."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, CONF_VERIFY_SSL)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import (CONF_CONTROLLER, CONF_POE_CONTROL, CONF_SITE_ID,
                    CONTROLLER_ID, DOMAIN, LOGGER)
from .controller import UniFiController, get_controller
from .errors import (
    AlreadyConfigured, AuthenticationRequired, CannotConnect, UserLevel)

DEFAULT_PORT = 8443
DEFAULT_SITE_ID = 'default'
DEFAULT_VERIFY_SSL = False

REQUIREMENTS = ['aiounifi==4']


async def async_setup(hass, config):
    """Component doesn't support configuration through configuration.yaml."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up the UniFi component."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    controller = UniFiController(hass, config_entry)

    controller_id = CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID]
    )

    hass.data[DOMAIN][controller_id] = controller

    if not await controller.async_setup():
        return False

    if controller.mac is None:
        return True

    device_registry = await \
        hass.helpers.device_registry.async_get_registry()
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, controller.mac)},
        manufacturer='Ubiquiti',
        model="UniFi Controller",
        name="UniFi Controller",
        # sw_version=config.raw['swversion'],
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    controller_id = CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID]
    )
    controller = hass.data[DOMAIN].pop(controller_id)
    return await controller.async_reset()


@config_entries.HANDLERS.register(DOMAIN)
class UnifiFlowHandler(config_entries.ConfigFlow):
    """Handle a UniFi config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the UniFi flow."""
        self.config = None
        self.desc = None
        self.sites = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            try:
                self.config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_PORT: user_input.get(CONF_PORT),
                    CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL),
                    CONF_SITE_ID: DEFAULT_SITE_ID,
                }
                controller = await get_controller(self.hass, **self.config)

                self.sites = await controller.sites()

                return await self.async_step_site()

            except AuthenticationRequired:
                errors['base'] = 'faulty_credentials'

            except CannotConnect:
                errors['base'] = 'service_unavailable'

            except Exception:  # pylint: disable=broad-except
                LOGGER.error(
                    'Unknown error connecting with UniFi Controller at %s',
                    user_input[CONF_HOST])
                return self.async_abort(reason='unknown')

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Optional(
                    CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
            }),
            errors=errors,
        )

    async def async_step_site(self, user_input=None):
        """Select site to control."""
        errors = {}

        if user_input is not None:

            try:
                desc = user_input.get(CONF_SITE_ID, self.desc)
                for site in self.sites.values():
                    if desc == site['desc']:
                        if site['role'] != 'admin':
                            raise UserLevel
                        self.config[CONF_SITE_ID] = site['name']
                        break

                for entry in self._async_current_entries():
                    controller = entry.data[CONF_CONTROLLER]
                    if controller[CONF_HOST] == self.config[CONF_HOST] and \
                       controller[CONF_SITE_ID] == self.config[CONF_SITE_ID]:
                        raise AlreadyConfigured

                data = {
                    CONF_CONTROLLER: self.config,
                    CONF_POE_CONTROL: True
                }

                return self.async_create_entry(
                    title=desc,
                    data=data
                )

            except AlreadyConfigured:
                return self.async_abort(reason='already_configured')

            except UserLevel:
                return self.async_abort(reason='user_privilege')

        if len(self.sites) == 1:
            self.desc = next(iter(self.sites.values()))['desc']
            return await self.async_step_site(user_input={})

        sites = []
        for site in self.sites.values():
            sites.append(site['desc'])

        return self.async_show_form(
            step_id='site',
            data_schema=vol.Schema({
                vol.Required(CONF_SITE_ID): vol.In(sites)
            }),
            errors=errors,
        )
