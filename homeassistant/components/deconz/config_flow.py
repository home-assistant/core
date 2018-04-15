"""Config flow to configure deCONZ component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.helpers import aiohttp_client
from homeassistant.util.json import load_json

from .const import CONFIG_FILE, DOMAIN


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(entry.data['host'] for entry
               in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class DeconzFlowHandler(config_entries.ConfigFlowHandler):
    """Handle a deCONZ config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the deCONZ config flow."""
        self.bridges = []
        self.deconz_config = {}

    async def async_step_init(self, user_input=None):
        """Handle a deCONZ config flow start."""
        from pydeconz.utils import async_discovery

        if DOMAIN in self.hass.data:
            return self.async_abort(reason='one_instance_only')

        if user_input is not None:
            for bridge in self.bridges:
                if bridge[CONF_HOST] == user_input[CONF_HOST]:
                    self.deconz_config = bridge
                    return await self.async_step_link()

        session = aiohttp_client.async_get_clientsession(self.hass)
        self.bridges = await async_discovery(session)

        if len(self.bridges) == 1:
            self.deconz_config = self.bridges[0]
            return await self.async_step_link()
        elif len(self.bridges) > 1:
            hosts = []
            for bridge in self.bridges:
                hosts.append(bridge[CONF_HOST])
            return self.async_show_form(
                step_id='init',
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): vol.In(hosts)
                })
            )

        return self.async_abort(
            reason='no_bridges'
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the deCONZ bridge."""
        from pydeconz.utils import async_get_api_key
        errors = {}

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api_key = await async_get_api_key(session, **self.deconz_config)
            if api_key:
                self.deconz_config[CONF_API_KEY] = api_key
                return self.async_create_entry(
                    title='deCONZ',
                    data=self.deconz_config
                )
            errors['base'] = 'no_key'

        return self.async_show_form(
            step_id='link',
            errors=errors,
        )

    async def async_step_discovery(self, discovery_info):
        """Prepare configuration for a discovered deCONZ bridge.

        This flow is triggered by the discovery component.
        """
        deconz_config = {}
        deconz_config[CONF_HOST] = discovery_info.get(CONF_HOST)
        deconz_config[CONF_PORT] = discovery_info.get(CONF_PORT)
        deconz_config['bridgeid'] = discovery_info.get('serial')

        config_file = await self.hass.async_add_job(
            load_json, self.hass.config.path(CONFIG_FILE))
        if config_file and config_file[CONF_HOST] == deconz_config[CONF_HOST]:
            deconz_config = config_file

        if deconz_config[CONF_HOST] in configured_hosts(self.hass):
            return self.async_abort(reason='already_configured')

        return await self.async_step_import(deconz_config)

    async def async_step_import(self, import_config):
        """Import a deCONZ bridge as a config entry.

        This flow is triggered by `async_setup` for configured bridges.
        This flow is also triggered by `async_step_discovery`.

        This will execute for any bridge that does not have a
        config entry yet (based on host).

        If an API key is provided, we will create an entry.
        Otherwise we will delegate to `link` step which
        will ask user to link the bridge.
        """
        if CONF_API_KEY not in import_config:
            self.deconz_config = import_config
            return await self.async_step_link()
        return self.async_create_entry(
            title='deCONZ',
            data=import_config
        )
