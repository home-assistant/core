"""Config flow for AWTRIX integration."""

from collections.abc import Mapping
import logging
from pprint import pformat
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries

# from homeassistant.components import dhcp
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult

from .awtrix_api import ApiAuthenticationFailed, AwtrixAPI, ApiCannotConnect
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_MANUAL_INPUT = "Manually configure AWTRIX3 device"


class AwtrixConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AWTRIX."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry

    def __init__(self) -> None:
        """Init discovery flow."""
        self.device_id = None
        self.devices = []
        self.awtrix_config = {}
        self._discovered_device: tuple[dict[str, Any], str] | None = None

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Lan coordinator."""

        self._discovered_device = {
            CONF_DEVICE_ID: discovery_info.properties.get("id"),
            CONF_NAME: discovery_info.properties.get("name"),
            CONF_HOST: discovery_info.host
        }

        await self.async_set_unique_id(self._discovered_device["device_id"])
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = self._discovered_device

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input=None) -> ConfigFlowResult:
        """Confirm discovery."""

        device = self._discovered_device

        self.device_id = device[CONF_DEVICE_ID]
        self.awtrix_config = {
            CONF_NAME: device[CONF_NAME],
            CONF_HOST: device[CONF_HOST],
        }

        return await self.async_step_configure()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        """Handle auto discovery."""

        if user_input:
            if user_input[CONF_HOST] == CONF_MANUAL_INPUT:
                return await self.async_step_configure()

            for device in self.devices:
                if device[CONF_HOST] == user_input[CONF_HOST]:
                    self.device_id = device[CONF_DEVICE_ID]
                    self.awtrix_config = {
                        CONF_NAME: device[CONF_NAME],
                        CONF_HOST: device[CONF_HOST],
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

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Discovered AWTRIX devices %s",
                          pformat(self.devices))

        if self.devices:
            devices = {CONF_MANUAL_INPUT: CONF_MANUAL_INPUT}
            for device in self.devices:
                description = f"{device[CONF_NAME]} ({device[CONF_HOST]})"
                # if hardware := device[CONF_HARDWARE]:
                #    description += f" [{hardware}]"
                devices[device[CONF_HOST]] = description

            return self.async_show_form(
                step_id="device",
                data_schema=vol.Schema(
                    {vol.Optional(CONF_HOST): vol.In(devices)}),
            )

        return await self.async_step_configure()

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Device configuration."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input:
            self.awtrix_config = user_input
            errors, description_placeholders = await self.async_setup_profiles()
            if not errors:
                title = f"{self.device_id}"
                return self.async_create_entry(title=title, data=self.awtrix_config)

        def conf(name, default=None):
            return self.awtrix_config.get(name, default)

        # Username and Password are optional and default empty
        # See https://github.com/home-assistant/core/issues/39182
        # and https://github.com/home-assistant/core/issues/35904
        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=conf(CONF_HOST)): str,
                    vol.Optional(CONF_USERNAME, default=conf(CONF_USERNAME, "")): str,
                    vol.Optional(CONF_PASSWORD, default=conf(CONF_PASSWORD, "")): str,
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_setup_profiles(
        self, configure_unique_id: bool = True
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Fetch AWTRIX device profiles."""

        api = AwtrixAPI(
            self.hass,
            self.awtrix_config[CONF_HOST],
            80,
            self.awtrix_config[CONF_USERNAME],
            self.awtrix_config[CONF_PASSWORD],
        )

        try:
            info = await api.get_data()
            if info is None:
                raise AbortFlow(reason="no_device_info")

            if not self.device_id:
                self.device_id = info["uid"]

            if configure_unique_id:
                await self.async_set_unique_id(self.device_id, raise_on_progress=False)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: self.awtrix_config[CONF_HOST],
                        CONF_NAME: self.device_id,
                        CONF_USERNAME: self.awtrix_config[CONF_USERNAME],
                        CONF_PASSWORD: self.awtrix_config[CONF_PASSWORD],
                    }
                )

            return {}, {}  # noqa: TRY300
        except ApiAuthenticationFailed:
            description_placeholders = {
                "error": "Could not authenticate with AWTRIX device."}
            return {CONF_PASSWORD: "auth_failed"}, description_placeholders
        except ApiCannotConnect:
            return {"base": "awtrix_error"}, {"error": "Cannot connect to AWTRIX device."}

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication of an existing config entry."""
        reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert reauth_entry is not None
        self._reauth_entry = reauth_entry
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth."""
        entry = self._reauth_entry
        errors: dict[str, str] | None = {}
        description_placeholders: dict[str, str] | None = None
        if user_input is not None:
            entry_data = entry.data
            self.awtrix_config = entry_data | user_input
            errors, description_placeholders = await self.async_setup_profiles(
                configure_unique_id=False
            )
            if not errors:
                return self.async_update_reload_and_abort(entry, data=self.awtrix_config)

        username = (user_input or {}).get(
            CONF_USERNAME) or entry.data[CONF_USERNAME]
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=username): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )


async def async_discovery(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return if there are devices that can be discovered."""
    devices = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                         socket.IPPROTO_UDP)  # UDP
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(5)

    sock.bind(('', 4211))

    msg = b'FIND_AWTRIX'
    sock.sendto(msg, ("255.255.255.255", 4210))
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            device = {
                CONF_DEVICE_ID: data.decode('ascii'),
                CONF_NAME: data.decode('ascii'),
                CONF_HOST: addr[0],
            }
            devices.append(device)
        except Exception:  # noqa: BLE001
            break

    return devices
