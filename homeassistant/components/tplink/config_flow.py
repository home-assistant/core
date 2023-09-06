"""Config flow for TP-Link."""
from __future__ import annotations

from typing import Any

from kasa import SmartDevice, SmartDeviceException
from kasa.discover import Discover
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType

from . import (
    async_discover_devices,
    encrypt_credentials,
    get_credentials,
)
from .const import (
    DOMAIN,
    TPLINK_CLOUD_CREDENTIALS_SYNC,
    TPLINK_CLOUD_PASSWORD,
    TPLINK_CLOUD_USERNAME,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tplink."""

    VERSION = 1

    reauth_entry: config_entries.ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, SmartDevice] = {}
        self._discovered_device: SmartDevice | None = None
        # self._auth_credentials: AuthCredentials = AuthCredentials()

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Handle discovery via dhcp."""
        return await self._async_handle_discovery(
            discovery_info.ip, discovery_info.macaddress
        )

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle integration discovery."""
        return await self._async_handle_discovery(
            discovery_info[CONF_HOST], discovery_info[CONF_MAC]
        )

    async def _async_handle_discovery(self, host: str, mac: str) -> FlowResult:
        """Handle any discovery."""
        await self.async_set_unique_id(dr.format_mac(mac))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")

        try:
            self._discovered_device = await self._async_try_connect(
                host, raise_on_progress=True
            )
        except SmartDeviceException:
            return self.async_abort(reason="cannot_connect")
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        if user_input is not None:
            return self._async_create_entry_from_device(self._discovered_device)

        self._set_confirm_only()
        placeholders = {
            "name": self._discovered_device.alias,
            "model": self._discovered_device.model,
            "host": self._discovered_device.host,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if not (host := user_input[CONF_HOST]):
                return await self.async_step_pick_device()
            try:
                device = await self._async_try_connect(host, raise_on_progress=False)
            except SmartDeviceException:
                errors["base"] = "cannot_connect"
            else:
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""

        if user_input is None:
            # reauth_device = self.hass.data[DOMAIN][self.reauth_entry.entry_id].device
            placeholders = {
                "name": self.reauth_entry.title,
                "model": "",
                "host": self.reauth_entry.data.get(CONF_HOST),
            }
            self.context["title_placeholders"] = placeholders
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        return self.async_abort(reason="reauth_pending")

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            mac = user_input[CONF_DEVICE]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            return self._async_create_entry_from_device(self._discovered_devices[mac])

        configured_devices = {
            entry.unique_id for entry in self._async_current_entries()
        }
        self._discovered_devices = await async_discover_devices(self.hass)
        devices_name = {
            formatted_mac: (
                f"{device.alias} {device.model} ({device.host}) {formatted_mac}"
            )
            for formatted_mac, device in self._discovered_devices.items()
            if formatted_mac not in configured_devices
        }
        # Check if there is at least one device
        if not devices_name:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE): vol.In(devices_name)}),
        )

    @callback
    def _async_create_entry_from_device(self, device: SmartDevice) -> FlowResult:
        """Create a config entry from a smart device."""
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.host})
        return self.async_create_entry(
            title=f"{device.alias} {device.model}",
            data={
                CONF_HOST: device.host,
            },
        )

    async def _async_try_connect(
        self, host: str, raise_on_progress: bool = True
    ) -> SmartDevice:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: host})

        credentials = get_credentials(self.hass)
        device: SmartDevice = await Discover.discover_single(
            host, credentials=credentials
        )
        await self.async_set_unique_id(
            dr.format_mac(device.mac), raise_on_progress=raise_on_progress
        )
        return device

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="", data=encrypt_credentials(user_input)
            )

        credentials = get_credentials(self.hass, self.config_entry)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        TPLINK_CLOUD_USERNAME,
                        default=credentials.username,
                    ): str,
                    vol.Optional(
                        TPLINK_CLOUD_PASSWORD,
                        default=credentials.password,
                    ): str,
                    vol.Required(
                        TPLINK_CLOUD_CREDENTIALS_SYNC,
                        default=self.config_entry.options.get(
                            TPLINK_CLOUD_CREDENTIALS_SYNC
                        )
                        or True,
                    ): bool,
                }
            ),
        )
