"""Config flow to configure deCONZ component."""
import asyncio
from pprint import pformat
from urllib.parse import urlparse

import async_timeout
from pydeconz.errors import RequestError, ResponseError
from pydeconz.utils import (
    async_discovery,
    async_get_api_key,
    async_get_bridge_id,
    normalize_bridge_id,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_BRIDGE_ID,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

DECONZ_MANUFACTURERURL = "http://www.dresden-elektronik.de"
CONF_SERIAL = "serial"


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
        self.bridge_id = None
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
                    self.bridge_id = bridge[CONF_BRIDGE_ID]
                    self.deconz_config = {
                        CONF_HOST: bridge[CONF_HOST],
                        CONF_PORT: bridge[CONF_PORT],
                    }
                    return await self.async_step_link()

            self.deconz_config = user_input
            return await self.async_step_link()

        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            with async_timeout.timeout(10):
                self.bridges = await async_discovery(session)

        except (asyncio.TimeoutError, ResponseError):
            self.bridges = []

        LOGGER.debug("Discovered deCONZ gateways %s", pformat(self.bridges))

        if len(self.bridges) == 1:
            return await self.async_step_user(self.bridges[0])

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

        LOGGER.debug(
            "Preparing linking with deCONZ gateway %s", pformat(self.deconz_config)
        )

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
        if not self.bridge_id:
            session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                with async_timeout.timeout(10):
                    self.bridge_id = await async_get_bridge_id(
                        session, **self.deconz_config
                    )
                    await self.async_set_unique_id(self.bridge_id)

                    self._abort_if_unique_id_configured(
                        updates={
                            CONF_HOST: self.deconz_config[CONF_HOST],
                            CONF_PORT: self.deconz_config[CONF_PORT],
                            CONF_API_KEY: self.deconz_config[CONF_API_KEY],
                        }
                    )

            except asyncio.TimeoutError:
                return self.async_abort(reason="no_bridges")

        return self.async_create_entry(title=self.bridge_id, data=self.deconz_config)

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered deCONZ bridge."""
        if (
            discovery_info.get(ssdp.ATTR_UPNP_MANUFACTURER_URL)
            != DECONZ_MANUFACTURERURL
        ):
            return self.async_abort(reason="not_deconz_bridge")

        LOGGER.debug("deCONZ SSDP discovery %s", pformat(discovery_info))

        self.bridge_id = normalize_bridge_id(discovery_info[ssdp.ATTR_UPNP_SERIAL])
        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])

        entry = await self.async_set_unique_id(self.bridge_id)
        if entry and entry.source == "hassio":
            return self.async_abort(reason="already_configured")

        self._abort_if_unique_id_configured(
            updates={CONF_HOST: parsed_url.hostname, CONF_PORT: parsed_url.port}
        )

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
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
        LOGGER.debug("deCONZ HASSIO discovery %s", pformat(user_input))

        self.bridge_id = normalize_bridge_id(user_input[CONF_SERIAL])
        await self.async_set_unique_id(self.bridge_id)

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_API_KEY: user_input[CONF_API_KEY],
            }
        )

        self._hassio_discovery = user_input

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(self, user_input=None):
        """Confirm a Hass.io discovery."""
        if user_input is not None:
            self.deconz_config = {
                CONF_HOST: self._hassio_discovery[CONF_HOST],
                CONF_PORT: self._hassio_discovery[CONF_PORT],
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
