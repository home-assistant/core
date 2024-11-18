"""Config flow to configure songpal component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from songpal import Device, SongpalException
import voluptuous as vol

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME

from .const import CONF_ENDPOINT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SongpalConfig:
    """Device Configuration."""

    def __init__(self, name: str, host: str | None, endpoint: str) -> None:
        """Initialize Configuration."""
        self.name = name
        if TYPE_CHECKING:
            assert host is not None
        self.host = host
        self.endpoint = endpoint


class SongpalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Songpal configuration flow."""

    VERSION = 1

    conf: SongpalConfig

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        # Check if already configured
        self._async_abort_entries_match({CONF_ENDPOINT: self.conf.endpoint})
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

    async def async_step_ssdp(
        self, discovery_info: ssdp.SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Songpal device."""
        await self.async_set_unique_id(discovery_info.upnp[ssdp.ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Discovered: %s", discovery_info)

        friendly_name = discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]
        hostname = urlparse(discovery_info.ssdp_location).hostname
        scalarweb_info = discovery_info.upnp["X_ScalarWebAPI_DeviceInfo"]
        endpoint = scalarweb_info["X_ScalarWebAPI_BaseURL"]
        service_types = scalarweb_info["X_ScalarWebAPI_ServiceList"][
            "X_ScalarWebAPI_ServiceType"
        ]

        # Ignore Bravia TVs
        if "videoScreen" in service_types:
            return self.async_abort(reason="not_songpal_device")

        if TYPE_CHECKING:
            # the hostname must be str because the ssdp_location is not bytes and
            # not a relative url
            assert isinstance(hostname, str)

        self.context["title_placeholders"] = {
            CONF_NAME: friendly_name,
            CONF_HOST: hostname,
        }

        self.conf = SongpalConfig(friendly_name, hostname, endpoint)

        return await self.async_step_init()

    async def async_step_import(self, import_data: dict[str, str]) -> ConfigFlowResult:
        """Import a config entry."""
        name = import_data.get(CONF_NAME)
        endpoint = import_data[CONF_ENDPOINT]
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

        return await self.async_step_init(import_data)
