"""Config flow for TP-Link."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kasa import (
    AuthenticationException,
    Credentials,
    DeviceConfig,
    Discover,
    SmartDevice,
    SmartDeviceException,
    TimeoutException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_ALIAS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType

from . import (
    async_discover_devices,
    create_async_tplink_clientsession,
    get_credentials,
    mac_alias,
    set_credentials,
)
from .const import CONF_DEVICE_CONFIG, CONNECT_TIMEOUT, DOMAIN

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tplink."""

    VERSION = 1
    MINOR_VERSION = 2
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, SmartDevice] = {}
        self._discovered_device: SmartDevice | None = None

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
            discovery_info[CONF_HOST],
            discovery_info[CONF_MAC],
            discovery_info[CONF_DEVICE_CONFIG],
        )

    @callback
    def _update_config_if_entry_in_setup_error(
        self, entry: ConfigEntry, host: str, config: dict
    ) -> None:
        """If discovery encounters a device that is in SETUP_ERROR update the device config."""
        if entry.state is not ConfigEntryState.SETUP_ERROR:
            return
        entry_data = entry.data
        entry_config_dict = entry_data.get(CONF_DEVICE_CONFIG)
        if entry_config_dict == config and entry_data[CONF_HOST] == host:
            return
        self.hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_DEVICE_CONFIG: config, CONF_HOST: host}
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(entry.entry_id),
            f"config entry reload {entry.title} {entry.domain} {entry.entry_id}",
        )
        raise AbortFlow("already_configured")

    async def _async_handle_discovery(
        self, host: str, formatted_mac: str, config: dict | None = None
    ) -> FlowResult:
        """Handle any discovery."""
        current_entry = await self.async_set_unique_id(
            formatted_mac, raise_on_progress=False
        )
        if config and current_entry:
            self._update_config_if_entry_in_setup_error(current_entry, host, config)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._async_abort_entries_match({CONF_HOST: host})
        self.context[CONF_HOST] = host
        for progress in self._async_in_progress():
            if progress.get("context", {}).get(CONF_HOST) == host:
                return self.async_abort(reason="already_in_progress")
        credentials = await get_credentials(self.hass)
        try:
            await self._async_try_discover_and_update(
                host, credentials, raise_on_progress=True
            )
        except AuthenticationException:
            return await self.async_step_discovery_auth_confirm()
        except SmartDeviceException:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that auth is required."""
        assert self._discovered_device is not None
        errors = {}

        credentials = await get_credentials(self.hass)
        if credentials and credentials != self._discovered_device.config.credentials:
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationException:
                pass  # Authentication exceptions should continue to the rest of the step
            else:
                self._discovered_device = device
                return await self.async_step_discovery_confirm()

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationException:
                errors[CONF_PASSWORD] = "invalid_auth"
            except SmartDeviceException:
                errors["base"] = "cannot_connect"
            else:
                self._discovered_device = device
                await set_credentials(self.hass, username, password)
                self.hass.async_create_task(self._async_reload_requires_auth_entries())
                return await self.async_step_discovery_confirm()

        placeholders = self._async_make_placeholders_from_discovery()
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_auth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    def _async_make_placeholders_from_discovery(self) -> dict[str, str]:
        """Make placeholders for the discovery steps."""
        discovered_device = self._discovered_device
        assert discovered_device is not None
        return {
            "name": discovered_device.alias or mac_alias(discovered_device.mac),
            "model": discovered_device.model,
            "host": discovered_device.host,
        }

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovered_device is not None
        if user_input is not None:
            return self._async_create_entry_from_device(self._discovered_device)

        self._set_confirm_only()
        placeholders = self._async_make_placeholders_from_discovery()
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
            self._async_abort_entries_match({CONF_HOST: host})
            self.context[CONF_HOST] = host
            credentials = await get_credentials(self.hass)
            try:
                device = await self._async_try_discover_and_update(
                    host, credentials, raise_on_progress=False
                )
            except AuthenticationException:
                return await self.async_step_user_auth_confirm()
            except SmartDeviceException:
                errors["base"] = "cannot_connect"
            else:
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_user_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that auth is required."""
        errors = {}
        host = self.context[CONF_HOST]
        assert self._discovered_device is not None
        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationException:
                errors[CONF_PASSWORD] = "invalid_auth"
            except SmartDeviceException:
                errors["base"] = "cannot_connect"
            else:
                await set_credentials(self.hass, username, password)
                self.hass.async_create_task(self._async_reload_requires_auth_entries())
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user_auth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={CONF_HOST: host},
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step to pick discovered device."""
        if user_input is not None:
            mac = user_input[CONF_DEVICE]
            await self.async_set_unique_id(mac, raise_on_progress=False)
            self._discovered_device = self._discovered_devices[mac]
            host = self._discovered_device.host

            self.context[CONF_HOST] = host
            credentials = await get_credentials(self.hass)

            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationException:
                return await self.async_step_user_auth_confirm()
            except SmartDeviceException:
                return self.async_abort(reason="cannot_connect")
            return self._async_create_entry_from_device(device)

        configured_devices = {
            entry.unique_id for entry in self._async_current_entries()
        }
        self._discovered_devices = await async_discover_devices(self.hass)
        devices_name = {
            formatted_mac: (
                f"{device.alias or mac_alias(device.mac)} {device.model} ({device.host}) {formatted_mac}"
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

    async def _async_reload_requires_auth_entries(self) -> None:
        """Reload any in progress config flow that now have credentials."""
        _config_entries = self.hass.config_entries

        if reauth_entry := self.reauth_entry:
            await _config_entries.async_reload(reauth_entry.entry_id)

        for flow in _config_entries.flow.async_progress_by_handler(
            DOMAIN, include_uninitialized=True
        ):
            context: dict[str, Any] = flow["context"]
            if context.get("source") != SOURCE_REAUTH:
                continue
            entry_id: str = context["entry_id"]
            if entry := _config_entries.async_get_entry(entry_id):
                await _config_entries.async_reload(entry.entry_id)
                if entry.state is ConfigEntryState.LOADED:
                    _config_entries.flow.async_abort(flow["flow_id"])

    @callback
    def _async_create_entry_from_device(self, device: SmartDevice) -> FlowResult:
        """Create a config entry from a smart device."""
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.host})
        return self.async_create_entry(
            title=f"{device.alias} {device.model}",
            data={
                CONF_HOST: device.host,
                CONF_ALIAS: device.alias,
                CONF_MODEL: device.model,
                CONF_DEVICE_CONFIG: device.config.to_dict(
                    credentials_hash=device.credentials_hash,
                    exclude_credentials=True,
                ),
            },
        )

    async def _async_try_discover_and_update(
        self,
        host: str,
        credentials: Credentials | None,
        raise_on_progress: bool,
    ) -> SmartDevice:
        """Try to discover the device and call update.

        Will try to connect to legacy devices if discovery fails.
        """
        try:
            self._discovered_device = await Discover.discover_single(
                host, credentials=credentials
            )
        except TimeoutException:
            # Try connect() to legacy devices if discovery fails
            self._discovered_device = await SmartDevice.connect(
                config=DeviceConfig(host)
            )
        else:
            if self._discovered_device.config.uses_http:
                self._discovered_device.config.http_client = (
                    create_async_tplink_clientsession(self.hass)
                )
            await self._discovered_device.update()
        await self.async_set_unique_id(
            dr.format_mac(self._discovered_device.mac),
            raise_on_progress=raise_on_progress,
        )
        return self._discovered_device

    async def _async_try_connect(
        self,
        discovered_device: SmartDevice,
        credentials: Credentials | None,
    ) -> SmartDevice:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: discovered_device.host})

        config = discovered_device.config
        if credentials:
            config.credentials = credentials
        config.timeout = CONNECT_TIMEOUT
        if config.uses_http:
            config.http_client = create_async_tplink_clientsession(self.hass)

        self._discovered_device = await SmartDevice.connect(config=config)
        await self.async_set_unique_id(
            dr.format_mac(self._discovered_device.mac),
            raise_on_progress=False,
        )
        return self._discovered_device

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Start the reauthentication flow if the device needs updated credentials."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        reauth_entry = self.reauth_entry
        assert reauth_entry is not None
        entry_data = reauth_entry.data
        host = entry_data[CONF_HOST]

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            try:
                await self._async_try_discover_and_update(
                    host,
                    credentials=credentials,
                    raise_on_progress=True,
                )
            except AuthenticationException:
                errors[CONF_PASSWORD] = "invalid_auth"
            except SmartDeviceException:
                errors["base"] = "cannot_connect"
            else:
                await set_credentials(self.hass, username, password)
                self.hass.async_create_task(self._async_reload_requires_auth_entries())
                return self.async_abort(reason="reauth_successful")

        # Old config entries will not have these values.
        alias = entry_data.get(CONF_ALIAS) or "unknown"
        model = entry_data.get(CONF_MODEL) or "unknown"

        placeholders = {"name": alias, "model": model, "host": host}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )
