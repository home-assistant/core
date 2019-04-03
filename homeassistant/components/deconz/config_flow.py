"""Config flow to configure deCONZ component."""
import asyncio

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ALLOW_CLIP_SENSOR, CONF_ALLOW_DECONZ_GROUPS, CONF_BRIDGEID,
    DEFAULT_ALLOW_CLIP_SENSOR, DEFAULT_ALLOW_DECONZ_GROUPS, DEFAULT_PORT,
    DOMAIN)


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(entry.data[CONF_HOST] for entry
               in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class DeconzFlowHandler(config_entries.ConfigFlow):
    """Handle a deCONZ config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    _hassio_discovery = None

    def __init__(self):
        """Initialize the deCONZ config flow."""
        self.bridges = []
        self.deconz_config = {}

    async def async_step_user(self, user_input=None):
        """Handle a deCONZ config flow start.

        Only allows one instance to be set up.
        If only one bridge is found go to link step.
        If more than one bridge is found let user choose bridge to link.
        If no bridge is found allow user to manually input configuration.
        """
        from pydeconz.utils import async_discovery

        if configured_hosts(self.hass):
            return self.async_abort(reason='one_instance_only')

        if user_input is not None:
            for bridge in self.bridges:
                if bridge[CONF_HOST] == user_input[CONF_HOST]:
                    self.deconz_config = bridge
                    return await self.async_step_link()

            self.deconz_config = user_input
            return await self.async_step_link()

        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            with async_timeout.timeout(10):
                self.bridges = await async_discovery(session)

        except asyncio.TimeoutError:
            self.bridges = []

        if len(self.bridges) == 1:
            self.deconz_config = self.bridges[0]
            return await self.async_step_link()

        if len(self.bridges) > 1:
            hosts = []

            for bridge in self.bridges:
                hosts.append(bridge[CONF_HOST])

            return self.async_show_form(
                step_id='init',
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): vol.In(hosts)
                })
            )

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }),
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the deCONZ bridge."""
        from pydeconz.errors import ResponseError, RequestError
        from pydeconz.utils import async_get_api_key
        errors = {}

        if user_input is not None:
            if configured_hosts(self.hass):
                return self.async_abort(reason='one_instance_only')

            session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                with async_timeout.timeout(10):
                    api_key = await async_get_api_key(
                        session, **self.deconz_config)

            except (ResponseError, RequestError, asyncio.TimeoutError):
                errors['base'] = 'no_key'

            else:
                self.deconz_config[CONF_API_KEY] = api_key
                return await self.async_step_options()

        return self.async_show_form(
            step_id='link',
            errors=errors,
        )

    async def async_step_options(self, user_input=None):
        """Extra options for deCONZ.

        CONF_CLIP_SENSOR -- Allow user to choose if they want clip sensors.
        CONF_DECONZ_GROUPS -- Allow user to choose if they want deCONZ groups.
        """
        from pydeconz.utils import async_get_bridgeid

        if user_input is not None:
            self.deconz_config[CONF_ALLOW_CLIP_SENSOR] = \
                user_input[CONF_ALLOW_CLIP_SENSOR]
            self.deconz_config[CONF_ALLOW_DECONZ_GROUPS] = \
                user_input[CONF_ALLOW_DECONZ_GROUPS]

            if CONF_BRIDGEID not in self.deconz_config:
                session = aiohttp_client.async_get_clientsession(self.hass)
                try:
                    with async_timeout.timeout(10):
                        self.deconz_config[CONF_BRIDGEID] = \
                            await async_get_bridgeid(
                                session, **self.deconz_config)

                except asyncio.TimeoutError:
                    return self.async_abort(reason='no_bridges')

            return self.async_create_entry(
                title='deCONZ-' + self.deconz_config[CONF_BRIDGEID],
                data=self.deconz_config
            )

        return self.async_show_form(
            step_id='options',
            data_schema=vol.Schema({
                vol.Optional(CONF_ALLOW_CLIP_SENSOR,
                             default=DEFAULT_ALLOW_CLIP_SENSOR): bool,
                vol.Optional(CONF_ALLOW_DECONZ_GROUPS,
                             default=DEFAULT_ALLOW_DECONZ_GROUPS): bool,
            }),
        )

    async def async_step_discovery(self, discovery_info):
        """Prepare configuration for a discovered deCONZ bridge.

        This flow is triggered by the discovery component.
        """
        deconz_config = {}
        deconz_config[CONF_HOST] = discovery_info.get(CONF_HOST)
        deconz_config[CONF_PORT] = discovery_info.get(CONF_PORT)
        deconz_config[CONF_BRIDGEID] = discovery_info.get('serial')

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
        if configured_hosts(self.hass):
            return self.async_abort(reason='one_instance_only')

        self.deconz_config = import_config
        if CONF_API_KEY not in import_config:
            return await self.async_step_link()

        user_input = {CONF_ALLOW_CLIP_SENSOR: True,
                      CONF_ALLOW_DECONZ_GROUPS: True}
        return await self.async_step_options(user_input=user_input)

    async def async_step_hassio(self, user_input=None):
        """Prepare configuration for a Hass.io deCONZ bridge.

        This flow is triggered by the discovery component.
        """
        if configured_hosts(self.hass):
            return self.async_abort(reason='one_instance_only')

        self._hassio_discovery = user_input

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm a Hass.io discovery."""
        if user_input is not None:
            data = self._hassio_discovery

            return self.async_create_entry(
                title=data['addon'], data={
                    CONF_HOST: data[CONF_HOST],
                    CONF_PORT: data[CONF_PORT],
                    CONF_BRIDGEID: data['serial'],
                    CONF_API_KEY: data[CONF_API_KEY],
                    CONF_ALLOW_CLIP_SENSOR:
                        user_input[CONF_ALLOW_CLIP_SENSOR],
                    CONF_ALLOW_DECONZ_GROUPS:
                        user_input[CONF_ALLOW_DECONZ_GROUPS],
                })

        return self.async_show_form(
            step_id='hassio_confirm',
            description_placeholders={
                'addon': self._hassio_discovery['addon']
            },
            data_schema=vol.Schema({
                vol.Optional(CONF_ALLOW_CLIP_SENSOR,
                             default=DEFAULT_ALLOW_CLIP_SENSOR): bool,
                vol.Optional(CONF_ALLOW_DECONZ_GROUPS,
                             default=DEFAULT_ALLOW_DECONZ_GROUPS): bool,
            })
        )
