"""Config flow for TP-Link."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kasa import (
    AuthenticationError,
    Credentials,
    Device,
    DeviceConfig,
    Discover,
    KasaException,
    TimeoutError,
)
import voluptuous as vol

from homeassistant.components import dhcp
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
)
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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import DiscoveryInfoType

from . import (
    async_discover_devices,
    create_async_tplink_clientsession,
    get_credentials,
    mac_alias,
    set_credentials,
)
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_CREDENTIALS_HASH,
    CONF_DEVICE_CONFIG,
    CONNECT_TIMEOUT,
    DOMAIN,
)

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class TPLinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tplink."""

    VERSION = 1
    MINOR_VERSION = 4
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Device] = {}
        self._discovered_device: Device | None = None

    async def async_step_dhcp(
        self, discovery_info: dhcp.DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""
        return await self._async_handle_discovery(
            discovery_info.ip, dr.format_mac(discovery_info.macaddress)
        )

    async def async_step_integration_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        return await self._async_handle_discovery(
            discovery_info[CONF_HOST],
            discovery_info[CONF_MAC],
            discovery_info[CONF_DEVICE_CONFIG],
        )

    @callback
    def _update_config_if_entry_in_setup_error(
        self, entry: ConfigEntry, host: str, config: dict
    ) -> ConfigFlowResult | None:
        """If discovery encounters a device that is in SETUP_ERROR or SETUP_RETRY update the device config."""
        if entry.state not in (
            ConfigEntryState.SETUP_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ):
            return None
        entry_data = entry.data
        entry_config_dict = entry_data.get(CONF_DEVICE_CONFIG)
        if entry_config_dict == config and entry_data[CONF_HOST] == host:
            return None
        updates = {**entry.data, CONF_DEVICE_CONFIG: config, CONF_HOST: host}
        # If the connection parameters have changed the credentials_hash will be invalid.
        if (
            entry_config_dict
            and isinstance(entry_config_dict, dict)
            and entry_config_dict.get(CONF_CONNECTION_TYPE)
            != config.get(CONF_CONNECTION_TYPE)
        ):
            updates.pop(CONF_CREDENTIALS_HASH, None)
        return self.async_update_reload_and_abort(
            entry,
            data=updates,
            reason="already_configured",
        )

    async def _async_handle_discovery(
        self, host: str, formatted_mac: str, config: dict | None = None
    ) -> ConfigFlowResult:
        """Handle any discovery."""
        current_entry = await self.async_set_unique_id(
            formatted_mac, raise_on_progress=False
        )
        if (
            config
            and current_entry
            and (
                result := self._update_config_if_entry_in_setup_error(
                    current_entry, host, config
                )
            )
        ):
            return result
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
        except AuthenticationError:
            return await self.async_step_discovery_auth_confirm()
        except KasaException:
            return self.async_abort(reason="cannot_connect")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that auth is required."""
        assert self._discovered_device is not None
        errors = {}

        credentials = await get_credentials(self.hass)
        if credentials and credentials != self._discovered_device.config.credentials:
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationError:
                pass  # Authentication exceptions should continue to the rest of the step
            else:
                self._discovered_device = device
                return await self.async_step_discovery_confirm()

        placeholders = self._async_make_placeholders_from_discovery()

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationError as ex:
                errors[CONF_PASSWORD] = "invalid_auth"
                placeholders["error"] = str(ex)
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                self._discovered_device = device
                await set_credentials(self.hass, username, password)
                self.hass.async_create_task(
                    self._async_reload_requires_auth_entries(), eager_start=False
                )
                return self._async_create_entry_from_device(self._discovered_device)

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
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

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
            except AuthenticationError:
                return await self.async_step_user_auth_confirm()
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_HOST, default=""): str}),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_user_auth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that auth is required."""
        errors: dict[str, str] = {}
        host = self.context[CONF_HOST]
        placeholders: dict[str, str] = {CONF_HOST: host}

        assert self._discovered_device is not None
        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            credentials = Credentials(username, password)
            try:
                device = await self._async_try_connect(
                    self._discovered_device, credentials
                )
            except AuthenticationError as ex:
                errors[CONF_PASSWORD] = "invalid_auth"
                placeholders["error"] = str(ex)
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                await set_credentials(self.hass, username, password)
                self.hass.async_create_task(
                    self._async_reload_requires_auth_entries(), eager_start=False
                )
                return self._async_create_entry_from_device(device)

        return self.async_show_form(
            step_id="user_auth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            except AuthenticationError:
                return await self.async_step_user_auth_confirm()
            except KasaException:
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
    def _async_create_entry_from_device(self, device: Device) -> ConfigFlowResult:
        """Create a config entry from a smart device."""
        # This is only ever called after a successful device update so we know that
        # the credential_hash is correct and should be saved.
        self._abort_if_unique_id_configured(updates={CONF_HOST: device.host})
        data = {
            CONF_HOST: device.host,
            CONF_ALIAS: device.alias,
            CONF_MODEL: device.model,
            CONF_DEVICE_CONFIG: device.config.to_dict(
                exclude_credentials=True,
            ),
        }
        if device.credentials_hash:
            data[CONF_CREDENTIALS_HASH] = device.credentials_hash
        return self.async_create_entry(
            title=f"{device.alias} {device.model}",
            data=data,
        )

    async def _async_try_discover_and_update(
        self,
        host: str,
        credentials: Credentials | None,
        raise_on_progress: bool,
    ) -> Device:
        """Try to discover the device and call update.

        Will try to connect to legacy devices if discovery fails.
        """
        try:
            self._discovered_device = await Discover.discover_single(
                host, credentials=credentials
            )
        except TimeoutError:
            # Try connect() to legacy devices if discovery fails
            self._discovered_device = await Device.connect(config=DeviceConfig(host))
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
        discovered_device: Device,
        credentials: Credentials | None,
    ) -> Device:
        """Try to connect."""
        self._async_abort_entries_match({CONF_HOST: discovered_device.host})

        config = discovered_device.config
        if credentials:
            config.credentials = credentials
        config.timeout = CONNECT_TIMEOUT
        if config.uses_http:
            config.http_client = create_async_tplink_clientsession(self.hass)

        self._discovered_device = await Device.connect(config=config)
        await self.async_set_unique_id(
            dr.format_mac(self._discovered_device.mac),
            raise_on_progress=False,
        )
        return self._discovered_device

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start the reauthentication flow if the device needs updated credentials."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
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
            except AuthenticationError as ex:
                errors[CONF_PASSWORD] = "invalid_auth"
                placeholders["error"] = str(ex)
            except KasaException as ex:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(ex)
            else:
                await set_credentials(self.hass, username, password)
                self.hass.async_create_task(
                    self._async_reload_requires_auth_entries(), eager_start=False
                )
                return self.async_abort(reason="reauth_successful")

        # Old config entries will not have these values.
        alias = entry_data.get(CONF_ALIAS) or "unknown"
        model = entry_data.get(CONF_MODEL) or "unknown"

        placeholders.update({"name": alias, "model": model, "host": host})

        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )
