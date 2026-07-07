"""Config flow for SMLIGHT Zigbee integration."""

from collections.abc import Mapping
from typing import Any, override

from pysmlight import Api2
from pysmlight.const import Devices
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .bluetooth import get_ble_scanner_mode
from .const import CONF_BLE_SCANNER_MODE, DOMAIN, BLEScannerMode
from .coordinator import SmConfigEntry

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)

STEP_AUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

BLE_SCANNER_OPTIONS = [
    BLEScannerMode.DISABLED,
    BLEScannerMode.AUTO,
    BLEScannerMode.ACTIVE,
    BLEScannerMode.PASSIVE,
]

BLE_SCANNER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BLE_SCANNER_MODE): SelectSelector(
            SelectSelectorConfig(
                options=BLE_SCANNER_OPTIONS,
                translation_key=CONF_BLE_SCANNER_MODE,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
    }
)


class SmlightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMLIGHT Zigbee."""

    _host: str
    _device_name: str
    client: Api2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self.client = Api2(self._host, session=async_get_clientsession(self.hass))

            try:
                if not await self._async_check_auth_required(user_input):
                    info = await self.client.get_info()
                    self._device_name = str(info.hostname)

                    if info.model not in Devices:
                        return self.async_abort(reason="unsupported_device")

                    return await self._async_complete_entry(user_input)
            except SmlightConnectionError:
                errors["base"] = "cannot_connect"
            except SmlightAuthError:
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authentication to SLZB-06 device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                if not await self._async_check_auth_required(user_input):
                    info = await self.client.get_info()
                    self._device_name = str(info.hostname)

                    if info.model not in Devices:
                        return self.async_abort(reason="unsupported_device")

                    if self.source == SOURCE_RECONFIGURE:
                        await self.async_set_unique_id(format_mac(info.MAC))
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(),
                            data_updates={
                                CONF_HOST: self._host,
                                **user_input,
                            },
                        )

                    return await self._async_complete_entry(user_input)
            except SmlightConnectionError:
                return self.async_abort(reason="cannot_connect")
            except SmlightAuthError:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth", data_schema=STEP_AUTH_DATA_SCHEMA, errors=errors
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered Lan coordinator."""
        mac: str | None = discovery_info.properties.get("mac")
        self._device_name = discovery_info.hostname.removesuffix(".local.")
        self._host = discovery_info.host

        self.context["title_placeholders"] = {CONF_NAME: self._device_name}
        self.client = Api2(self._host, session=async_get_clientsession(self.hass))

        # fallback for legacy firmware older than v2.3.x
        if mac is None:
            try:
                info = await self.client.get_info()
            except SmlightConnectionError:
                # User is likely running unsupported ESPHome firmware
                return self.async_abort(reason="cannot_connect")
            mac = info.MAC

        await self.async_set_unique_id(format_mac(mac))
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery confirm."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                if not await self._async_check_auth_required(user_input):
                    info = await self.client.get_info()

                    if info.model not in Devices:
                        return self.async_abort(reason="unsupported_device")

                return await self._async_complete_entry(user_input)

            except SmlightConnectionError:
                return self.async_abort(reason="cannot_connect")

            except SmlightAuthError:
                return await self.async_step_auth()

        self._set_confirm_only()

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders={"host": self._device_name},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when API Authentication failed."""

        self._host = entry_data[CONF_HOST]
        self.client = Api2(self._host, session=async_get_clientsession(self.hass))

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication of an existing config entry."""
        errors = {}
        if user_input is not None:
            try:
                await self.client.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except SmlightAuthError:
                errors["base"] = "invalid_auth"
            except SmlightConnectionError:
                return self.async_abort(reason="cannot_connect")
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_AUTH_DATA_SCHEMA,
            description_placeholders=self.context["title_placeholders"],
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of SMLIGHT device."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self.client = Api2(self._host, session=async_get_clientsession(self.hass))

            check_input = {**entry.data, **user_input}
            try:
                await self._async_check_auth_required(check_input)
                info = await self.client.get_info()
            except SmlightConnectionError:
                errors["base"] = "cannot_connect"
            except SmlightAuthError:
                return await self.async_step_auth()
            else:
                if info.model not in Devices:
                    return self.async_abort(reason="unsupported_device")

                await self.async_set_unique_id(format_mac(info.MAC))
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        # This should never happen since we only listen to DHCP requests
        # for configured devices.
        return self.async_abort(reason="already_configured")

    async def _async_check_auth_required(self, user_input: dict[str, Any]) -> bool:
        """Check if auth required and attempt to authenticate."""
        if await self.client.check_auth_needed():
            if user_input.get(CONF_USERNAME) and user_input.get(CONF_PASSWORD):
                return not await self.client.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            raise SmlightAuthError
        return False

    async def _async_complete_entry(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        info = await self.client.get_info()

        await self.async_set_unique_id(
            format_mac(info.MAC), raise_on_progress=self.source != SOURCE_USER
        )
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        user_input[CONF_HOST] = self._host

        assert info.model is not None
        title = self._device_name or info.model
        return self.async_create_entry(title=title, data=user_input)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: SmConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for SMLIGHT."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        coordinator = self.config_entry.runtime_data.data
        info = coordinator.data.info
        errors = {}

        if info.ble is None:
            return await self.async_step_no_settings()

        if user_input is not None:
            scanner_mode = user_input.get(CONF_BLE_SCANNER_MODE)
            if scanner_mode is not None:
                current_mode = get_ble_scanner_mode(self.config_entry, info)
                if scanner_mode != current_mode:
                    remote_adapter_enabled = scanner_mode != BLEScannerMode.DISABLED
                    try:
                        await coordinator.client.set_ble_proxy(remote_adapter_enabled)
                    except SmlightConnectionError, SmlightAuthError:
                        errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        suggested_values = {
            CONF_BLE_SCANNER_MODE: get_ble_scanner_mode(self.config_entry, info)
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                BLE_SCANNER_SCHEMA, user_input or suggested_values
            ),
            errors=errors,
        )

    async def async_step_no_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options for devices without settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        coordinator = self.config_entry.runtime_data.data
        return self.async_show_form(
            step_id="no_settings",
            data_schema=vol.Schema({}),
            description_placeholders={"model": coordinator.data.info.model},
        )
