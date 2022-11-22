"""Config flow to configure Axis devices."""
from __future__ import annotations

from collections.abc import Mapping
from ipaddress import ip_address
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp, ssdp, zeroconf
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util.network import is_link_local

from .const import (
    CONF_STREAM_PROFILE,
    CONF_VIDEO_SOURCE,
    DEFAULT_STREAM_PROFILE,
    DEFAULT_VIDEO_SOURCE,
    DOMAIN as AXIS_DOMAIN,
)
from .device import AxisNetworkDevice, get_axis_device
from .errors import AuthenticationRequired, CannotConnect

AXIS_OUI = {"00:40:8c", "ac:cc:8e", "b8:a4:4f"}
DEFAULT_PORT = 80


class AxisFlowHandler(config_entries.ConfigFlow, domain=AXIS_DOMAIN):
    """Handle a Axis config flow."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AxisOptionsFlowHandler:
        """Get the options flow for this handler."""
        return AxisOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize the Axis config flow."""
        self.device_config: dict[str, Any] = {}
        self.discovery_schema: dict[vol.Required, type[str | int]] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a Axis config flow start.

        Manage device specific parameters.
        """
        errors = {}

        if user_input is not None:
            try:
                device = await get_axis_device(self.hass, MappingProxyType(user_input))

                serial = device.vapix.serial_number
                await self.async_set_unique_id(format_mac(serial))

                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    }
                )

                self.device_config = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_MODEL: device.vapix.product_number,
                }

                return await self._create_entry(serial)

            except AuthenticationRequired:
                errors["base"] = "invalid_auth"

            except CannotConnect:
                errors["base"] = "cannot_connect"

        data = self.discovery_schema or {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user",
            description_placeholders=self.device_config,
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def _create_entry(self, serial: str) -> FlowResult:
        """Create entry for device.

        Generate a name to be used as a prefix for device entities.
        """
        model = self.device_config[CONF_MODEL]
        same_model = [
            entry.data[CONF_NAME]
            for entry in self.hass.config_entries.async_entries(AXIS_DOMAIN)
            if entry.source != SOURCE_IGNORE and entry.data[CONF_MODEL] == model
        ]

        name = model
        for idx in range(len(same_model) + 1):
            name = f"{model} {idx}"
            if name not in same_model:
                break

        self.device_config[CONF_NAME] = name

        title = f"{model} - {serial}"
        return self.async_create_entry(title=title, data=self.device_config)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Trigger a reauthentication flow."""
        self.context["title_placeholders"] = {
            CONF_NAME: entry_data[CONF_NAME],
            CONF_HOST: entry_data[CONF_HOST],
        }

        self.discovery_schema = {
            vol.Required(CONF_HOST, default=entry_data[CONF_HOST]): str,
            vol.Required(CONF_USERNAME, default=entry_data[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=entry_data[CONF_PORT]): int,
        }

        return await self.async_step_user()

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Prepare configuration for a DHCP discovered Axis device."""
        return await self._process_discovered_device(
            {
                CONF_HOST: discovery_info.ip,
                CONF_MAC: format_mac(discovery_info.macaddress),
                CONF_NAME: discovery_info.hostname,
                CONF_PORT: DEFAULT_PORT,
            }
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Prepare configuration for a SSDP discovered Axis device."""
        url = urlsplit(discovery_info.upnp[ssdp.ATTR_UPNP_PRESENTATION_URL])
        return await self._process_discovered_device(
            {
                CONF_HOST: url.hostname,
                CONF_MAC: format_mac(discovery_info.upnp[ssdp.ATTR_UPNP_SERIAL]),
                CONF_NAME: f"{discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]}",
                CONF_PORT: url.port,
            }
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Prepare configuration for a Zeroconf discovered Axis device."""
        return await self._process_discovered_device(
            {
                CONF_HOST: discovery_info.host,
                CONF_MAC: format_mac(discovery_info.properties["macaddress"]),
                CONF_NAME: discovery_info.name.split(".", 1)[0],
                CONF_PORT: discovery_info.port,
            }
        )

    async def _process_discovered_device(self, device: dict[str, Any]) -> FlowResult:
        """Prepare configuration for a discovered Axis device."""
        if device[CONF_MAC][:8] not in AXIS_OUI:
            return self.async_abort(reason="not_axis_device")

        if is_link_local(ip_address(device[CONF_HOST])):
            return self.async_abort(reason="link_local_address")

        await self.async_set_unique_id(device[CONF_MAC])

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: device[CONF_HOST],
                CONF_PORT: device[CONF_PORT],
            }
        )

        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: device[CONF_NAME],
                    CONF_HOST: device[CONF_HOST],
                },
                "configuration_url": f"http://{device[CONF_HOST]}:{device[CONF_PORT]}",
            }
        )

        self.discovery_schema = {
            vol.Required(CONF_HOST, default=device[CONF_HOST]): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=device[CONF_PORT]): int,
        }

        return await self.async_step_user()


class AxisOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Axis device options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Axis device options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.device: AxisNetworkDevice | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Axis device options."""
        self.device = self.hass.data[AXIS_DOMAIN][self.config_entry.unique_id]
        return await self.async_step_configure_stream()

    async def async_step_configure_stream(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Axis device stream options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        schema = {}

        assert self.device
        vapix = self.device.api.vapix

        # Stream profiles

        if vapix.stream_profiles or vapix.params.stream_profiles_max_groups > 0:
            stream_profiles = [DEFAULT_STREAM_PROFILE]
            for profile in vapix.streaming_profiles:
                stream_profiles.append(profile.name)

            schema[
                vol.Optional(
                    CONF_STREAM_PROFILE, default=self.device.option_stream_profile
                )
            ] = vol.In(stream_profiles)

        # Video sources

        if vapix.params.image_nbrofviews > 0:
            await vapix.params.update_image()

            video_sources = {DEFAULT_VIDEO_SOURCE: DEFAULT_VIDEO_SOURCE}
            for idx, video_source in vapix.params.image_sources.items():
                if not video_source["Enabled"]:
                    continue
                video_sources[idx + 1] = video_source["Name"]

            schema[
                vol.Optional(CONF_VIDEO_SOURCE, default=self.device.option_video_source)
            ] = vol.In(video_sources)

        return self.async_show_form(
            step_id="configure_stream", data_schema=vol.Schema(schema)
        )
