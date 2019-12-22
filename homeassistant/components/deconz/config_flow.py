"""Config flow to configure deCONZ component."""
import asyncio
from urllib.parse import urlparse

import async_timeout
from pydeconz.errors import RequestError, ResponseError
from pydeconz.utils import async_discovery, async_get_api_key, async_get_gateway_config
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    _LOGGER,
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_BRIDGEID,
    CONF_UUID,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DEFAULT_PORT,
    DOMAIN,
)

DECONZ_MANUFACTURERURL = "http://www.dresden-elektronik.de"
CONF_SERIAL = "serial"


@callback
def configured_gateways(hass):
    """Return a set of all configured gateways."""
    return {
        entry.data[CONF_BRIDGEID]: entry
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


@callback
def get_master_gateway(hass):
    """Return the gateway which is marked as master."""
    for gateway in hass.data[DOMAIN].values():
        if gateway.master:
            return gateway


class DeconzFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a deCONZ config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    _hassio_discovery = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return DeconzOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the deCONZ config flow."""
        self.bridges = []
        self.deconz_config = {}

    async def async_step_init(self, user_input=None):
        """Needed in order to not require re-translation of strings."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a deCONZ config flow start.

        If only one bridge is found go to link step.
        If more than one bridge is found let user choose bridge to link.
        If no bridge is found allow user to manually input configuration.
        """
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

        except (asyncio.TimeoutError, ResponseError):
            self.bridges = []

        if len(self.bridges) == 1:
            self.deconz_config = self.bridges[0]
            return await self.async_step_link()

        if len(self.bridges) > 1:
            hosts = []

            for bridge in self.bridges:
                hosts.append(bridge[CONF_HOST])

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({vol.Required(CONF_HOST): vol.In(hosts)}),
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the deCONZ bridge."""
        errors = {}

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                with async_timeout.timeout(10):
                    api_key = await async_get_api_key(session, **self.deconz_config)

            except (ResponseError, RequestError, asyncio.TimeoutError):
                errors["base"] = "no_key"

            else:
                self.deconz_config[CONF_API_KEY] = api_key
                return await self._create_entry()

        return self.async_show_form(step_id="link", errors=errors)

    async def _create_entry(self):
        """Create entry for gateway."""
        if CONF_BRIDGEID not in self.deconz_config:
            session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                with async_timeout.timeout(10):
                    gateway_config = await async_get_gateway_config(
                        session, **self.deconz_config
                    )
                    self.deconz_config[CONF_BRIDGEID] = gateway_config.bridgeid
                    self.deconz_config[CONF_UUID] = gateway_config.uuid

            except asyncio.TimeoutError:
                return self.async_abort(reason="no_bridges")

        return self.async_create_entry(
            title="deCONZ-" + self.deconz_config[CONF_BRIDGEID], data=self.deconz_config
        )

    def _update_entry(self, entry, host, port, api_key=None):
        """Update existing entry."""
        if (
            entry.data[CONF_HOST] == host
            and entry.data[CONF_PORT] == port
            and (api_key is None or entry.data[CONF_API_KEY] == api_key)
        ):
            return self.async_abort(reason="already_configured")

        entry.data[CONF_HOST] = host
        entry.data[CONF_PORT] = port

        if api_key is not None:
            entry.data[CONF_API_KEY] = api_key

        self.hass.config_entries.async_update_entry(entry)
        return self.async_abort(reason="updated_instance")

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered deCONZ bridge."""
        if discovery_info[ssdp.ATTR_UPNP_MANUFACTURER_URL] != DECONZ_MANUFACTURERURL:
            return self.async_abort(reason="not_deconz_bridge")

        uuid = discovery_info[ssdp.ATTR_UPNP_UDN].replace("uuid:", "")

        _LOGGER.debug("deCONZ gateway discovered (%s)", uuid)

        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if uuid == entry.data.get(CONF_UUID):
                if entry.source == "hassio":
                    return self.async_abort(reason="already_configured")
                return self._update_entry(entry, parsed_url.hostname, parsed_url.port)

        bridgeid = discovery_info[ssdp.ATTR_UPNP_SERIAL]
        if any(
            bridgeid == flow["context"][CONF_BRIDGEID]
            for flow in self._async_in_progress()
        ):
            return self.async_abort(reason="already_in_progress")

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context[CONF_BRIDGEID] = bridgeid
        self.context["title_placeholders"] = {"host": parsed_url.hostname}

        self.deconz_config = {
            CONF_HOST: parsed_url.hostname,
            CONF_PORT: parsed_url.port,
        }

        return await self.async_step_link()

    async def async_step_hassio(self, user_input=None):
        """Prepare configuration for a Hass.io deCONZ bridge.

        This flow is triggered by the discovery component.
        """
        bridgeid = user_input[CONF_SERIAL]
        gateway_entries = configured_gateways(self.hass)

        if bridgeid in gateway_entries:
            entry = gateway_entries[bridgeid]
            return self._update_entry(
                entry,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_API_KEY],
            )

        self._hassio_discovery = user_input

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm a Hass.io discovery."""
        if user_input is not None:
            self.deconz_config = {
                CONF_HOST: self._hassio_discovery[CONF_HOST],
                CONF_PORT: self._hassio_discovery[CONF_PORT],
                CONF_BRIDGEID: self._hassio_discovery[CONF_SERIAL],
                CONF_API_KEY: self._hassio_discovery[CONF_API_KEY],
            }

            return await self._create_entry()

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
        )


class DeconzOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle deCONZ options."""

    def __init__(self, config_entry):
        """Initialize deCONZ options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the deCONZ options."""
        return await self.async_step_deconz_devices()

    async def async_step_deconz_devices(self, user_input=None):
        """Manage the deconz devices options."""
        if user_input is not None:
            self.options[CONF_ALLOW_CLIP_SENSOR] = user_input[CONF_ALLOW_CLIP_SENSOR]
            self.options[CONF_ALLOW_DECONZ_GROUPS] = user_input[
                CONF_ALLOW_DECONZ_GROUPS
            ]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="deconz_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ALLOW_CLIP_SENSOR,
                        default=self.config_entry.options.get(
                            CONF_ALLOW_CLIP_SENSOR, DEFAULT_ALLOW_CLIP_SENSOR
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ALLOW_DECONZ_GROUPS,
                        default=self.config_entry.options.get(
                            CONF_ALLOW_DECONZ_GROUPS, DEFAULT_ALLOW_DECONZ_GROUPS
                        ),
                    ): bool,
                }
            ),
        )
