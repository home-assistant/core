"""Config flow for ONVIF."""
from __future__ import annotations

from pprint import pformat
from urllib.parse import urlparse

from onvif.exceptions import ONVIFError
import voluptuous as vol
from wsdiscovery.discovery import ThreadedWSDiscovery as WSDiscovery
from wsdiscovery.scope import Scope
from wsdiscovery.service import Service
from zeep.exceptions import Fault

from homeassistant import config_entries
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import (
    CONF_DEVICE_ID,
    CONF_RTSP_TRANSPORT,
    DEFAULT_ARGUMENTS,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
    RTSP_TRANS_PROTOCOLS,
)
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


async def async_discovery(hass) -> bool:
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
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OnvifOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the ONVIF config flow."""
        self.device_id = None
        self.devices = []
        self.onvif_config = {}

    async def async_step_user(self, user_input=None):
        """Handle user flow."""
        if user_input is not None:
            return await self.async_step_device()

        return self.async_show_form(step_id="user")

    async def async_step_device(self, user_input=None):
        """Handle WS-Discovery.

        Let user choose between discovered devices and manual configuration.
        If no device is found allow user to manually input configuration.
        """
        if user_input:

            if CONF_MANUAL_INPUT == user_input[CONF_HOST]:
                return await self.async_step_manual_input()

            for device in self.devices:
                name = f"{device[CONF_NAME]} ({device[CONF_HOST]})"
                if name == user_input[CONF_HOST]:
                    self.device_id = device[CONF_DEVICE_ID]
                    self.onvif_config = {
                        CONF_NAME: device[CONF_NAME],
                        CONF_HOST: device[CONF_HOST],
                        CONF_PORT: device[CONF_PORT],
                    }
                    return await self.async_step_auth()

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

        return await self.async_step_manual_input()

    async def async_step_manual_input(self, user_input=None):
        """Manual configuration."""
        if user_input:
            self.onvif_config = user_input
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="manual_input",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
        )

    async def async_step_auth(self, user_input=None):
        """Username and Password configuration for ONVIF device."""
        if user_input:
            self.onvif_config[CONF_USERNAME] = user_input[CONF_USERNAME]
            self.onvif_config[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            return await self.async_step_profiles()

        # Username and Password are optional and default empty
        # due to some cameras not allowing you to change ONVIF user settings.
        # See https://github.com/home-assistant/core/issues/39182
        # and https://github.com/home-assistant/core/issues/35904
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_USERNAME, default=""): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
        )

    async def async_step_profiles(self, user_input=None):
        """Fetch ONVIF device profiles."""
        errors = {}

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
                    for interface in network_interfaces:
                        if interface.Enabled:
                            self.device_id = interface.Info.HwAddress
                except Fault as fault:
                    if "not implemented" not in fault.message:
                        raise fault

                    LOGGER.debug(
                        "Couldn't get network interfaces from ONVIF deivice '%s'. Error: %s",
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

            await device.close()

            title = f"{self.onvif_config[CONF_NAME]} - {self.device_id}"
            return self.async_create_entry(title=title, data=self.onvif_config)

        except ONVIFError as err:
            LOGGER.error(
                "Couldn't setup ONVIF device '%s'. Error: %s",
                self.onvif_config[CONF_NAME],
                err,
            )
            await device.close()
            return self.async_abort(reason="onvif_error")

        except Fault:
            errors["base"] = "cannot_connect"

        await device.close()
        return self.async_show_form(step_id="auth", errors=errors)

    async def async_step_import(self, user_input):
        """Handle import."""
        self.onvif_config = user_input
        return await self.async_step_profiles()


class OnvifOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle ONVIF options."""

    def __init__(self, config_entry):
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
            return self.async_create_entry(title="", data=self.options)

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
                            CONF_RTSP_TRANSPORT, RTSP_TRANS_PROTOCOLS[0]
                        ),
                    ): vol.In(RTSP_TRANS_PROTOCOLS),
                }
            ),
        )
