"""Config flow for ONVIF."""
from __future__ import annotations

from pprint import pformat
from typing import Any
from urllib.parse import urlparse

from onvif.exceptions import ONVIFError
import voluptuous as vol
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
from wsdiscovery.scope import Scope
from wsdiscovery.service import Service
from zeep.exceptions import Fault

from homeassistant import config_entries
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.components.stream import (
    CONF_RTSP_TRANSPORT,
    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
    RTSP_TRANSPORTS,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback

from .const import CONF_DEVICE_ID, DEFAULT_ARGUMENTS, DEFAULT_PORT, DOMAIN, LOGGER
from .device import get_device

CONF_MANUAL_INPUT = "Manually configure ONVIF device"


def wsdiscovery() -> list[Service]:
    """Get ONVIF Profile S devices from network."""
    discovery = WSDiscovery(ttl=4)
    discovery.start()
    services = discovery.searchServices(
        scopes=[Scope("onvif://www.onvif.org/Profile/Streaming")]
    )
    discovery.stop()
    return services


async def async_discovery(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return if there are devices that can be discovered."""
    LOGGER.debug("Starting ONVIF discovery")
    services = await hass.async_add_executor_job(wsdiscovery)

    devices = []
    for service in services:
        url = urlparse(service.getXAddrs()[0])
        device = {
            CONF_DEVICE_ID: None,
            CONF_NAME: service.getEPR(),
            CONF_HOST: url.hostname,
            CONF_PORT: url.port or 80,
        }
        for scope in service.getScopes():
            scope_str = scope.getValue()
            if scope_str.lower().startswith("onvif://www.onvif.org/name"):
                device[CONF_NAME] = scope_str.split("/")[-1]
            if scope_str.lower().startswith("onvif://www.onvif.org/mac"):
                device[CONF_DEVICE_ID] = scope_str.split("/")[-1]
        devices.append(device)

    return devices


class OnvifFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a ONVIF config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OnvifOptionsFlowHandler:
        """Get the options flow for this handler."""
        return OnvifOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the ONVIF config flow."""
        self.device_id = None
        self.devices = []
        self.onvif_config = {}

    async def async_step_user(self, user_input=None):
        """Handle user flow."""
        if user_input:
            if user_input["auto"]:
                return await self.async_step_device()
            return await self.async_step_configure()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("auto", default=True): bool}),
        )

    async def async_step_device(self, user_input=None):
        """Handle WS-Discovery.

        Let user choose between discovered devices and manual configuration.
        If no device is found allow user to manually input configuration.
        """
        if user_input:
            if user_input[CONF_HOST] == CONF_MANUAL_INPUT:
                return await self.async_step_configure()

            for device in self.devices:
                name = f"{device[CONF_NAME]} ({device[CONF_HOST]})"
                if name == user_input[CONF_HOST]:
                    self.device_id = device[CONF_DEVICE_ID]
                    self.onvif_config = {
                        CONF_NAME: device[CONF_NAME],
                        CONF_HOST: device[CONF_HOST],
                        CONF_PORT: device[CONF_PORT],
                    }
                    return await self.async_step_configure()

        discovery = await async_discovery(self.hass)
        for device in discovery:
            configured = any(
                entry.unique_id == device[CONF_DEVICE_ID]
                for entry in self._async_current_entries()
            )

            if not configured:
                self.devices.append(device)

        LOGGER.debug("Discovered ONVIF devices %s", pformat(self.devices))

        if self.devices:
            names = [
                f"{device[CONF_NAME]} ({device[CONF_HOST]})" for device in self.devices
            ]

            names.append(CONF_MANUAL_INPUT)

            return self.async_show_form(
                step_id="device",
                data_schema=vol.Schema({vol.Optional(CONF_HOST): vol.In(names)}),
            )

        return await self.async_step_configure()

    async def async_step_configure(self, user_input=None):
        """Device configuration."""
        errors = {}
        if user_input:
            self.onvif_config = user_input
            try:
                return await self.async_setup_profiles()
            except Fault:
                errors["base"] = "cannot_connect"

        def conf(name, default=None):
            return self.onvif_config.get(name, default)

        # Username and Password are optional and default empty
        # due to some cameras not allowing you to change ONVIF user settings.
        # See https://github.com/home-assistant/core/issues/39182
        # and https://github.com/home-assistant/core/issues/35904
        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=conf(CONF_NAME)): str,
                    vol.Required(CONF_HOST, default=conf(CONF_HOST)): str,
                    vol.Required(CONF_PORT, default=conf(CONF_PORT, DEFAULT_PORT)): int,
                    vol.Optional(CONF_USERNAME, default=conf(CONF_USERNAME, "")): str,
                    vol.Optional(CONF_PASSWORD, default=conf(CONF_PASSWORD, "")): str,
                }
            ),
            errors=errors,
        )

    async def async_setup_profiles(self):
        """Fetch ONVIF device profiles."""
        LOGGER.debug(
            "Fetching profiles from ONVIF device %s", pformat(self.onvif_config)
        )

        device = get_device(
            self.hass,
            self.onvif_config[CONF_HOST],
            self.onvif_config[CONF_PORT],
            self.onvif_config[CONF_USERNAME],
            self.onvif_config[CONF_PASSWORD],
        )

        try:
            await device.update_xaddrs()
            device_mgmt = device.create_devicemgmt_service()

            # Get the MAC address to use as the unique ID for the config flow
            if not self.device_id:
                try:
                    network_interfaces = await device_mgmt.GetNetworkInterfaces()
                    interface = next(
                        filter(lambda interface: interface.Enabled, network_interfaces),
                        None,
                    )
                    if interface:
                        self.device_id = interface.Info.HwAddress
                except Fault as fault:
                    if "not implemented" not in fault.message:
                        raise fault

                    LOGGER.debug(
                        (
                            "Couldn't get network interfaces from ONVIF deivice '%s'."
                            " Error: %s"
                        ),
                        self.onvif_config[CONF_NAME],
                        fault,
                    )

            # If no network interfaces are exposed, fallback to serial number
            if not self.device_id:
                device_info = await device_mgmt.GetDeviceInformation()
                self.device_id = device_info.SerialNumber

            if not self.device_id:
                return self.async_abort(reason="no_mac")

            await self.async_set_unique_id(self.device_id, raise_on_progress=False)
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: self.onvif_config[CONF_HOST],
                    CONF_PORT: self.onvif_config[CONF_PORT],
                    CONF_NAME: self.onvif_config[CONF_NAME],
                }
            )

            # Verify there is an H264 profile
            media_service = device.create_media_service()
            profiles = await media_service.GetProfiles()
            h264 = any(
                profile.VideoEncoderConfiguration
                and profile.VideoEncoderConfiguration.Encoding == "H264"
                for profile in profiles
            )

            if not h264:
                return self.async_abort(reason="no_h264")

            title = f"{self.onvif_config[CONF_NAME]} - {self.device_id}"
            return self.async_create_entry(title=title, data=self.onvif_config)

        except ONVIFError as err:
            LOGGER.error(
                "Couldn't setup ONVIF device '%s'. Error: %s",
                self.onvif_config[CONF_NAME],
                err,
            )
            return self.async_abort(reason="onvif_error")

        finally:
            await device.close()


class OnvifOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle ONVIF options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize ONVIF options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the ONVIF options."""
        return await self.async_step_onvif_devices()

    async def async_step_onvif_devices(self, user_input=None):
        """Manage the ONVIF devices options."""
        if user_input is not None:
            self.options[CONF_EXTRA_ARGUMENTS] = user_input[CONF_EXTRA_ARGUMENTS]
            self.options[CONF_RTSP_TRANSPORT] = user_input[CONF_RTSP_TRANSPORT]
            self.options[CONF_USE_WALLCLOCK_AS_TIMESTAMPS] = user_input.get(
                CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
                self.config_entry.options.get(CONF_USE_WALLCLOCK_AS_TIMESTAMPS, False),
            )
            return self.async_create_entry(title="", data=self.options)

        advanced_options = {}
        if self.show_advanced_options:
            advanced_options[
                vol.Optional(
                    CONF_USE_WALLCLOCK_AS_TIMESTAMPS,
                    default=self.config_entry.options.get(
                        CONF_USE_WALLCLOCK_AS_TIMESTAMPS, False
                    ),
                )
            ] = bool
        return self.async_show_form(
            step_id="onvif_devices",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_EXTRA_ARGUMENTS,
                        default=self.config_entry.options.get(
                            CONF_EXTRA_ARGUMENTS, DEFAULT_ARGUMENTS
                        ),
                    ): str,
                    vol.Optional(
                        CONF_RTSP_TRANSPORT,
                        default=self.config_entry.options.get(
                            CONF_RTSP_TRANSPORT, next(iter(RTSP_TRANSPORTS))
                        ),
                    ): vol.In(RTSP_TRANSPORTS),
                    **advanced_options,
                }
            ),
        )
