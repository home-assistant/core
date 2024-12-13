"""Config flow for Improv via BLE integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from bleak import BleakError
from improv_ble_client import (
    SERVICE_DATA_UUID,
    Error,
    ImprovBLEClient,
    ImprovServiceData,
    State,
    device_filter,
    errors as improv_ble_errors,
)
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_PROVISION_SCHEMA = vol.Schema(
    {
        vol.Required("ssid"): str,
        vol.Optional("password"): str,
    }
)


@dataclass
class Credentials:
    """Container for WiFi credentials."""

    password: str
    ssid: str


class ImprovBLEConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Improv via BLE."""

    VERSION = 1

    _authorize_task: asyncio.Task | None = None
    _can_identify: bool | None = None
    _credentials: Credentials | None = None
    _provision_result: ConfigFlowResult | None = None
    _provision_task: asyncio.Task | None = None
    _reauth_entry: ConfigEntry | None = None
    _remove_bluetooth_callback: Callable[[], None] | None = None
    _unsub: Callable[[], None] | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._device: ImprovBLEClient | None = None
        # Populated by user step
        self._discovered_devices: dict[str, bluetooth.BluetoothServiceInfoBleak] = {}
        # Populated by bluetooth, reauth_confirm and user steps
        self._discovery_info: bluetooth.BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            # Guard against the user selecting a device which has been configured by
            # another flow.
            self._abort_if_unique_id_configured()
            self._discovery_info = self._discovered_devices[address]
            return await self.async_step_start_improv()

        current_addresses = self._async_current_ids()
        for discovery in bluetooth.async_discovered_service_info(self.hass):
            if (
                discovery.address in current_addresses
                or discovery.address in self._discovered_devices
                or not device_filter(discovery.advertisement)
            ):
                continue
            self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name} ({service_info.address})"
                        )
                        for service_info in self._discovered_devices.values()
                    }
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    def _abort_if_provisioned(self) -> None:
        """Check improv state and abort flow if needed."""
        # mypy is not aware that we can't get here without having these set already
        assert self._discovery_info is not None

        service_data = self._discovery_info.service_data
        try:
            improv_service_data = ImprovServiceData.from_bytes(
                service_data[SERVICE_DATA_UUID]
            )
        except improv_ble_errors.InvalidCommand as err:
            _LOGGER.warning(
                "Aborting improv flow, device %s sent invalid improv data: '%s'",
                self._discovery_info.address,
                service_data[SERVICE_DATA_UUID].hex(),
            )
            raise AbortFlow("invalid_improv_data") from err

        if improv_service_data.state in (State.PROVISIONING, State.PROVISIONED):
            _LOGGER.debug(
                "Aborting improv flow, device %s is already provisioned: %s",
                self._discovery_info.address,
                improv_service_data.state,
            )
            raise AbortFlow("already_provisioned")

    @callback
    def _async_update_ble(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a ble callback."""
        _LOGGER.debug(
            "Got updated BLE data: %s",
            service_info.service_data[SERVICE_DATA_UUID].hex(),
        )

        self._discovery_info = service_info
        try:
            self._abort_if_provisioned()
        except AbortFlow:
            self.hass.config_entries.flow.async_abort(self.flow_id)

    def _unregister_bluetooth_callback(self) -> None:
        """Unregister bluetooth callbacks."""
        if not self._remove_bluetooth_callback:
            return
        self._remove_bluetooth_callback()
        self._remove_bluetooth_callback = None

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the Bluetooth discovery step."""
        self._discovery_info = discovery_info

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._abort_if_provisioned()

        self._remove_bluetooth_callback = bluetooth.async_register_callback(
            self.hass,
            self._async_update_ble,
            bluetooth.BluetoothCallbackMatcher(
                {bluetooth.match.ADDRESS: discovery_info.address}
            ),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )

        name = self._discovery_info.name or self._discovery_info.address
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle bluetooth confirm step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._discovery_info is not None

        if user_input is None:
            name = self._discovery_info.name or self._discovery_info.address
            return self.async_show_form(
                step_id="bluetooth_confirm",
                description_placeholders={"name": name},
            )

        self._unregister_bluetooth_callback()
        return await self.async_step_start_improv()

    async def async_step_start_improv(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start improv flow.

        If the device supports identification, show a menu, if it does not,
        ask for WiFi credentials.
        """
        # mypy is not aware that we can't get here without having these set already
        assert self._discovery_info is not None

        if not self._device:
            self._device = ImprovBLEClient(self._discovery_info.device)
        device = self._device

        if self._can_identify is None:
            try:
                self._can_identify = await self._try_call(device.can_identify())
            except AbortFlow as err:
                return self.async_abort(reason=err.reason)
        if self._can_identify:
            return await self.async_step_main_menu()
        return await self.async_step_provision()

    async def async_step_main_menu(self, _: None = None) -> ConfigFlowResult:
        """Show the main menu."""
        return self.async_show_menu(
            step_id="main_menu",
            menu_options=[
                "identify",
                "provision",
            ],
        )

    async def async_step_identify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle identify step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._device is not None

        if user_input is None:
            try:
                await self._try_call(self._device.identify())
            except AbortFlow as err:
                return self.async_abort(reason=err.reason)
            return self.async_show_form(step_id="identify")
        return await self.async_step_start_improv()

    async def async_step_provision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle provision step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._device is not None

        if user_input is None and self._credentials is None:
            return self.async_show_form(
                step_id="provision", data_schema=STEP_PROVISION_SCHEMA
            )
        if user_input is not None:
            self._credentials = Credentials(
                user_input.get("password", ""), user_input["ssid"]
            )

        try:
            need_authorization = await self._try_call(self._device.need_authorization())
        except AbortFlow as err:
            return self.async_abort(reason=err.reason)
        _LOGGER.debug("Need authorization: %s", need_authorization)
        if need_authorization:
            return await self.async_step_authorize()
        return await self.async_step_do_provision()

    async def async_step_do_provision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Execute provisioning."""

        async def _do_provision() -> None:
            # mypy is not aware that we can't get here without having these set already
            assert self._credentials is not None
            assert self._device is not None

            errors = {}
            try:
                redirect_url = await self._try_call(
                    self._device.provision(
                        self._credentials.ssid, self._credentials.password, None
                    )
                )
            except AbortFlow as err:
                self._provision_result = self.async_abort(reason=err.reason)
                return
            except improv_ble_errors.ProvisioningFailed as err:
                if err.error == Error.NOT_AUTHORIZED:
                    _LOGGER.debug("Need authorization when calling provision")
                    self._provision_result = await self.async_step_authorize()
                    return
                if err.error == Error.UNABLE_TO_CONNECT:
                    self._credentials = None
                    errors["base"] = "unable_to_connect"
                else:
                    self._provision_result = self.async_abort(reason="unknown")
                    return
            else:
                _LOGGER.debug("Provision successful, redirect URL: %s", redirect_url)
                # Abort all flows in progress with same unique ID
                for flow in self._async_in_progress(include_uninitialized=True):
                    flow_unique_id = flow["context"].get("unique_id")
                    if (
                        flow["flow_id"] != self.flow_id
                        and self.unique_id == flow_unique_id
                    ):
                        self.hass.config_entries.flow.async_abort(flow["flow_id"])
                if redirect_url:
                    self._provision_result = self.async_abort(
                        reason="provision_successful_url",
                        description_placeholders={"url": redirect_url},
                    )
                    return
                self._provision_result = self.async_abort(reason="provision_successful")
                return
            self._provision_result = self.async_show_form(
                step_id="provision", data_schema=STEP_PROVISION_SCHEMA, errors=errors
            )
            return

        if not self._provision_task:
            self._provision_task = self.hass.async_create_task(
                _do_provision(), eager_start=False
            )

        if not self._provision_task.done():
            return self.async_show_progress(
                step_id="do_provision",
                progress_action="provisioning",
                progress_task=self._provision_task,
            )

        self._provision_task = None
        return self.async_show_progress_done(next_step_id="provision_done")

    async def async_step_provision_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the result of the provision step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._provision_result is not None

        result = self._provision_result
        self._provision_result = None
        return result

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle authorize step."""
        # mypy is not aware that we can't get here without having these set already
        assert self._device is not None

        _LOGGER.debug("Wait for authorization")
        if not self._authorize_task:
            authorized_event = asyncio.Event()

            def on_state_update(state: State) -> None:
                _LOGGER.debug("State update: %s", state.name)
                if state != State.AUTHORIZATION_REQUIRED:
                    authorized_event.set()

            try:
                self._unsub = await self._try_call(
                    self._device.subscribe_state_updates(on_state_update)
                )
            except AbortFlow as err:
                return self.async_abort(reason=err.reason)

            self._authorize_task = self.hass.async_create_task(
                authorized_event.wait(), eager_start=False
            )

        if not self._authorize_task.done():
            return self.async_show_progress(
                step_id="authorize",
                progress_action="authorize",
                progress_task=self._authorize_task,
            )

        self._authorize_task = None
        if self._unsub:
            self._unsub()
            self._unsub = None
        return self.async_show_progress_done(next_step_id="provision")

    @staticmethod
    async def _try_call[_T](func: Coroutine[Any, Any, _T]) -> _T:
        """Call the library and abort flow on common errors."""
        try:
            return await func
        except BleakError as err:
            _LOGGER.warning("BleakError", exc_info=err)
            raise AbortFlow("cannot_connect") from err
        except improv_ble_errors.CharacteristicMissingError as err:
            _LOGGER.warning("CharacteristicMissing", exc_info=err)
            raise AbortFlow("characteristic_missing") from err
        except improv_ble_errors.CommandFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected exception")
            raise AbortFlow("unknown") from err

    @callback
    def async_remove(self) -> None:
        """Notification that the flow has been removed."""
        self._unregister_bluetooth_callback()
