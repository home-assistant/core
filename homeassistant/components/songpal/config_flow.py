"""Config flow to configure songpal component."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from songpal import Device, SongpalException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ENDPOINT, CONF_URL, CONF_UUID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SongpalConfig:
    """Device Configuration."""

    def __init__(self, name, host, endpoint):
        """Initialize Configuration."""
        self.name = name
        self.host = host
        self.endpoint = endpoint
        self.url = url
        self.uuid = uuid

class SongpalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Songpal configuration flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the flow."""
        self.conf: SongpalConfig | None = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_ENDPOINT): str,vol.Optional(CONF_URL): str,vol.Optional(CONF_UUID): str}),
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
                        vol.Optional(
                            CONF_URL, default=user_input.get(CONF_URL, "")
                        ): str,
                        vol.Optional(
                            CONF_UUID, default=user_input.get(CONF_UUID, "")
                        ): str,
                    }
                ),
                errors={"base": "cannot_connect"},
            )

        self.conf = SongpalConfig(name, parsed_url.hostname, endpoint, url, uuid)

        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        # Check if already configured
        self._async_abort_entries_match({CONF_ENDPOINT: self.conf.endpoint})
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                description_placeholders={
                    CONF_NAME: self.conf.name,
                    CONF_HOST: self.conf.host,
                    CONF_URL: self.conf.url,
                    CONF_UUID: self.conf.uuid
                },
            )

        await self.async_set_unique_id(self.conf.endpoint)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self.conf.name,
            data={CONF_NAME: self.conf.name, CONF_ENDPOINT: self.conf.endpoint, CONF_URL: self.conf.url, CONF_UUID: self.conf.uuid},
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a discovered Songpal device."""
        await self.async_set_unique_id(discovery_info.upnp[ssdp.ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Discovered: %s", discovery_info)

        friendly_name = discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]
        uuid = discovery_info[ssdp.ATTR_UPNP_UDN]
        url = discovery_info[ssdp.ATTR_SSDP_LOCATION]
        parsed_url = urlparse(discovery_info.ssdp_location)
        scalarweb_info = discovery_info.upnp["X_ScalarWebAPI_DeviceInfo"]
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

        self.conf = SongpalConfig(friendly_name, parsed_url.hostname, endpoint, url, uuid)

        return await self.async_step_init()

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        name = user_input.get(CONF_NAME)
        endpoint = user_input.get(CONF_ENDPOINT)
        parsed_url = urlparse(endpoint)
        url= ""
        uuid= ""

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

        self.conf = SongpalConfig(name, parsed_url.hostname, endpoint, url, uuid)

        return await self.async_step_init(user_input)
