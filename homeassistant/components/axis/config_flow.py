"""Config flow to configure Axis devices."""

from __future__ import annotations

from collections.abc import Mapping
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_PRESENTATION_URL,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.network import is_link_local

from . import AxisConfigEntry
from .const import (
    CONF_STREAM_PROFILE,
    CONF_VIDEO_SOURCE,
    DEFAULT_STREAM_PROFILE,
    DEFAULT_VIDEO_SOURCE,
    DOMAIN as AXIS_DOMAIN,
)
from .errors import AuthenticationRequired, CannotConnect
from .hub import AxisHub, get_axis_api

AXIS_OUI = {"00:40:8c", "ac:cc:8e", "b8:a4:4f"}
DEFAULT_PORT = 443
DEFAULT_PROTOCOL = "https"
PROTOCOL_CHOICES = ["https", "http"]


class AxisFlowHandler(ConfigFlow, domain=AXIS_DOMAIN):
    """Handle a Axis config flow."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AxisOptionsFlowHandler:
        """Get the options flow for this handler."""
        return AxisOptionsFlowHandler()

    def __init__(self) -> None:
        """Initialize the Axis config flow."""
        self.config: dict[str, Any] = {}
        self.discovery_schema: VolDictType | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a Axis config flow start.

        Manage device specific parameters.
        """
        errors = {}

        if user_input is not None:
            try:
                api = await get_axis_api(self.hass, user_input)

            except AuthenticationRequired:
                errors["base"] = "invalid_auth"

            except CannotConnect:
                errors["base"] = "cannot_connect"

            else:
                serial = api.vapix.serial_number
                config = {
                    CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }

                await self.async_set_unique_id(format_mac(serial))

                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=config
                    )
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=config
                    )
                self._abort_if_unique_id_configured()

                self.config = config | {CONF_MODEL: api.vapix.product_number}

                return await self._create_entry(serial)

        data = self.discovery_schema or {
            vol.Required(CONF_PROTOCOL): vol.In(PROTOCOL_CHOICES),
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user",
            description_placeholders=self.config,
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def _create_entry(self, serial: str) -> ConfigFlowResult:
        """Create entry for device.

        Generate a name to be used as a prefix for device entities.
        """
        model = self.config[CONF_MODEL]
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

        self.config[CONF_NAME] = name

        title = f"{model} - {serial}"
        return self.async_create_entry(title=title, data=self.config)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trigger a reconfiguration flow."""
        return await self._redo_configuration(
            self._get_reconfigure_entry().data, keep_password=True
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Trigger a reauthentication flow."""
        self.context["title_placeholders"] = {
            CONF_NAME: entry_data[CONF_NAME],
            CONF_HOST: entry_data[CONF_HOST],
        }
        return await self._redo_configuration(entry_data, keep_password=False)

    async def _redo_configuration(
        self, entry_data: Mapping[str, Any], keep_password: bool
    ) -> ConfigFlowResult:
        """Re-run configuration step."""
        protocol = entry_data.get(CONF_PROTOCOL, "http")
        password = entry_data[CONF_PASSWORD] if keep_password else ""
        self.discovery_schema = {
            vol.Required(CONF_PROTOCOL, default=protocol): vol.In(PROTOCOL_CHOICES),
            vol.Required(CONF_HOST, default=entry_data[CONF_HOST]): str,
            vol.Required(CONF_USERNAME, default=entry_data[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD, default=password): str,
            vol.Required(CONF_PORT, default=entry_data[CONF_PORT]): int,
        }

        return await self.async_step_user()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a DHCP discovered Axis device."""
        return await self._process_discovered_device(
            {
                CONF_HOST: discovery_info.ip,
                CONF_MAC: format_mac(discovery_info.macaddress),
                CONF_NAME: discovery_info.hostname,
                CONF_PORT: 80,
            }
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a SSDP discovered Axis device."""
        url = urlsplit(discovery_info.upnp[ATTR_UPNP_PRESENTATION_URL])
        return await self._process_discovered_device(
            {
                CONF_HOST: url.hostname,
                CONF_MAC: format_mac(discovery_info.upnp[ATTR_UPNP_SERIAL]),
                CONF_NAME: f"{discovery_info.upnp[ATTR_UPNP_FRIENDLY_NAME]}",
                CONF_PORT: url.port,
            }
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a Zeroconf discovered Axis device."""
        return await self._process_discovered_device(
            {
                CONF_HOST: discovery_info.host,
                CONF_MAC: format_mac(discovery_info.properties["macaddress"]),
                CONF_NAME: discovery_info.name.split(".", 1)[0],
                CONF_PORT: discovery_info.port,
            }
        )

    async def _process_discovered_device(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Prepare configuration for a discovered Axis device."""
        if discovery_info[CONF_MAC][:8] not in AXIS_OUI:
            return self.async_abort(reason="not_axis_device")

        if is_link_local(ip_address(discovery_info[CONF_HOST])):
            return self.async_abort(reason="link_local_address")

        await self.async_set_unique_id(discovery_info[CONF_MAC])

        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info[CONF_HOST]}
        )

        self.context.update(
            {
                "title_placeholders": {
                    CONF_NAME: discovery_info[CONF_NAME],
                    CONF_HOST: discovery_info[CONF_HOST],
                },
                "configuration_url": f"http://{discovery_info[CONF_HOST]}:{discovery_info[CONF_PORT]}",
            }
        )

        self.discovery_schema = {
            vol.Required(CONF_PROTOCOL): vol.In(PROTOCOL_CHOICES),
            vol.Required(CONF_HOST, default=discovery_info[CONF_HOST]): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return await self.async_step_user()


class AxisOptionsFlowHandler(OptionsFlow):
    """Handle Axis device options."""

    config_entry: AxisConfigEntry
    hub: AxisHub

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Axis device options."""
        self.hub = self.config_entry.runtime_data
        return await self.async_step_configure_stream()

    async def async_step_configure_stream(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Axis device stream options."""
        if user_input is not None:
            return self.async_create_entry(data=self.config_entry.options | user_input)

        schema = {}

        vapix = self.hub.api.vapix

        # Stream profiles

        if vapix.stream_profiles or (
            (profiles := vapix.params.stream_profile_handler.get("0"))
            and profiles.max_groups > 0
        ):
            stream_profiles = [DEFAULT_STREAM_PROFILE]
            stream_profiles.extend(profile.name for profile in vapix.streaming_profiles)

            schema[
                vol.Optional(
                    CONF_STREAM_PROFILE, default=self.hub.config.stream_profile
                )
            ] = vol.In(stream_profiles)

        # Video sources

        if (
            properties := vapix.params.property_handler.get("0")
        ) and properties.image_number_of_views > 0:
            await vapix.params.image_handler.update()
            video_sources: dict[int | str, str] = {
                DEFAULT_VIDEO_SOURCE: DEFAULT_VIDEO_SOURCE
            }
            for idx, video_source in vapix.params.image_handler.items():
                if not video_source.enabled:
                    continue
                video_sources[int(idx) + 1] = video_source.name

            schema[
                vol.Optional(CONF_VIDEO_SOURCE, default=self.hub.config.video_source)
            ] = vol.In(video_sources)

        return self.async_show_form(
            step_id="configure_stream", data_schema=vol.Schema(schema)
        )
