"""Config flow to configure songpal component."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from songpal import Device, SongpalException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .const import CONF_ENDPOINT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SongpalConfig:
    """Device Configuration."""

    def __init__(self, name, host, endpoint):
        """Initialize Configuration."""
        self.name = name
        self.host = host
        self.endpoint = endpoint


class SongpalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Songpal configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the flow."""
        self.conf: SongpalConfig | None = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_ENDPOINT): str}),
            )

        # Validate input
        endpoint = user_input[CONF_ENDPOINT]
        parsed_url = urlparse(endpoint)

        # Try to connect and get device name
        try:
            device = Device(endpoint)
            await device.get_supported_methods()
            interface_info = await device.get_interface_information()
            name = interface_info.modelName
        except SongpalException as ex:
            _LOGGER.debug("Connection failed: %s", ex)
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_ENDPOINT, default=user_input.get(CONF_ENDPOINT, "")
                        ): str,
                    }
                ),
                errors={"base": "cannot_connect"},
            )

        self.conf = SongpalConfig(name, parsed_url.hostname, endpoint)

        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        # Check if already configured
        if self._async_endpoint_already_configured():
            return self.async_abort(reason="already_configured")

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                description_placeholders={
                    CONF_NAME: self.conf.name,
                    CONF_HOST: self.conf.host,
                },
            )

        await self.async_set_unique_id(self.conf.endpoint)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.conf.name,
            data={CONF_NAME: self.conf.name, CONF_ENDPOINT: self.conf.endpoint},
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Songpal device."""
        await self.async_set_unique_id(discovery_info[ssdp.ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Discovered: %s", discovery_info)

        friendly_name = discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]
        parsed_url = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION])
        scalarweb_info = discovery_info["X_ScalarWebAPI_DeviceInfo"]
        endpoint = scalarweb_info["X_ScalarWebAPI_BaseURL"]
        service_types = scalarweb_info["X_ScalarWebAPI_ServiceList"][
            "X_ScalarWebAPI_ServiceType"
        ]

        # Ignore Bravia TVs
        if "videoScreen" in service_types:
            return self.async_abort(reason="not_songpal_device")

        self.context["title_placeholders"] = {
            CONF_NAME: friendly_name,
            CONF_HOST: parsed_url.hostname,
        }

        self.conf = SongpalConfig(friendly_name, parsed_url.hostname, endpoint)

        return await self.async_step_init()

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        name = user_input.get(CONF_NAME)
        endpoint = user_input.get(CONF_ENDPOINT)
        parsed_url = urlparse(endpoint)

        # Try to connect to test the endpoint
        try:
            device = Device(endpoint)
            await device.get_supported_methods()
            # Get name
            if name is None:
                interface_info = await device.get_interface_information()
                name = interface_info.modelName
        except SongpalException as ex:
            _LOGGER.error("Import from yaml configuration failed: %s", ex)
            return self.async_abort(reason="cannot_connect")

        self.conf = SongpalConfig(name, parsed_url.hostname, endpoint)

        return await self.async_step_init(user_input)

    @callback
    def _async_endpoint_already_configured(self):
        """See if we already have an endpoint matching user input configured."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_ENDPOINT) == self.conf.endpoint:
                return True
        return False
