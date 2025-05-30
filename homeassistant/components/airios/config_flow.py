"""Config flow for the Airios integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyairios import Airios, AiriosException, AiriosRtuTransport, AiriosTcpTransport
from pyairios.constants import BindingStatus
from pyairios.exceptions import AiriosBindingException
from pyairios.node import ProductId
import serial
import serial.tools.list_ports
import voluptuous as vol

from homeassistant.components import usb
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_BRIDGE_RF_ADDRESS,
    CONF_DEFAULT_HOST,
    CONF_DEFAULT_NETWORK_MODBUS_ADDRESS,
    CONF_DEFAULT_PORT,
    CONF_DEFAULT_SERIAL_MODBUS_ADDRESS,
    CONF_RF_ADDRESS,
    DOMAIN,
    SUPPORTED_ACCESSORIES,
    SUPPORTED_UNITS,
    BridgeType,
)
from .coordinator import AiriosDataUpdateCoordinator

CONF_MANUAL_PATH = "Enter Manually"

_LOGGER = logging.getLogger(__name__)


class AiriosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Airios."""

    VERSION = 1

    _modbus_address: int

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["serial", "network"],
        )

    async def _finish(self, entry_data: dict[str, Any]):
        bridge_rf_address = entry_data[CONF_BRIDGE_RF_ADDRESS]
        return self.async_create_entry(
            title=f"Airios RF bridge ({bridge_rf_address:06X})",
            data=entry_data,
        )

    async def async_step_network(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when setting up a network bridge."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            modbus_address = user_input[CONF_ADDRESS]
            try:
                data = await self._async_validate_bridge_network(
                    host=host, port=port, modbus_address=modbus_address
                )
            except UnexpectedProductId:
                errors["base"] = "unexpected_product_id"
            except AiriosException:
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(data)

        conf_host = CONF_DEFAULT_HOST
        conf_port = CONF_DEFAULT_PORT
        conf_modbus_address = CONF_DEFAULT_NETWORK_MODBUS_ADDRESS
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=conf_host): str,
                vol.Required(CONF_PORT, default=conf_port): int,
                vol.Required(CONF_ADDRESS, default=conf_modbus_address): int,
            }
        )
        return self.async_show_form(
            step_id="network",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step when setting up serial configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            modbus_address = user_input[CONF_ADDRESS]
            user_selection = user_input[CONF_DEVICE]
            if user_selection == CONF_MANUAL_PATH:
                self._modbus_address = modbus_address
                return await self.async_step_serial_manual_path()

            dev_path = await self.hass.async_add_executor_job(
                usb.get_serial_by_id, user_selection
            )
            try:
                data = await self._async_validate_bridge_serial(
                    device=dev_path, modbus_address=modbus_address
                )
            except UnexpectedProductId:
                errors["base"] = "unexpected_product_id"
            except AiriosException:
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(data)

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = {
            port.device: usb.human_readable_device_name(
                port.device,
                port.serial_number,
                port.manufacturer,
                port.description,
                f"{port.vid}" if port.vid else None,
                f"{port.pid}" if port.pid else None,
            )
            for port in ports
        }

        list_of_ports[CONF_MANUAL_PATH] = CONF_MANUAL_PATH
        conf_device = vol.UNDEFINED
        conf_modbus_address = CONF_DEFAULT_SERIAL_MODBUS_ADDRESS
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE, default=conf_device): vol.In(list_of_ports),
                vol.Required(CONF_ADDRESS, default=conf_modbus_address): int,
            }
        )
        return self.async_show_form(
            step_id="serial",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_serial_manual_path(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select path manually."""
        errors: dict[str, str] = {}

        if user_input is not None:
            modbus_address = self._modbus_address
            device = user_input[CONF_DEVICE]
            try:
                data = await self._async_validate_bridge_serial(
                    device=device, modbus_address=modbus_address
                )
            except UnexpectedProductId:
                errors["base"] = "unexpected_product_id"
            except AiriosException:
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(data)

        conf_device = vol.UNDEFINED
        schema = vol.Schema({vol.Required(CONF_DEVICE, default=conf_device): str})
        return self.async_show_form(
            step_id="serial_manual_path",
            data_schema=schema,
            errors=errors,
        )

    async def _async_validate_bridge(self, api: Airios):
        result = await api.bridge.node_product_id()
        if result.value != ProductId.BRDG_02R13:
            raise UnexpectedProductId

        result = await api.bridge.node_rf_address()
        if result is None or result.value is None:
            raise UnexpectedProductId
        bridge_rf_address = result.value

        await self.async_set_unique_id(f"{bridge_rf_address}")
        self._abort_if_unique_id_configured()

        return bridge_rf_address

    async def _async_validate_bridge_serial(
        self,
        device: str,
        modbus_address: int,
    ) -> dict[str, Any]:
        transport = AiriosRtuTransport(device=device)
        api = Airios(transport, modbus_address)
        bridge_rf_address = await self._async_validate_bridge(api)
        data: dict[str, Any] = {
            CONF_TYPE: BridgeType.SERIAL,
            CONF_DEVICE: device,
            CONF_ADDRESS: modbus_address,
            CONF_BRIDGE_RF_ADDRESS: bridge_rf_address,
        }
        return data

    async def _async_validate_bridge_network(
        self,
        host: str,
        port: int,
        modbus_address: int,
    ) -> dict[str, Any]:
        transport = AiriosTcpTransport(host=host, port=port)
        api = Airios(transport, modbus_address)
        bridge_rf_address = await self._async_validate_bridge(api)
        data: dict[str, Any] = {
            CONF_TYPE: BridgeType.NETWORK,
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_ADDRESS: modbus_address,
            CONF_BRIDGE_RF_ADDRESS: bridge_rf_address,
        }
        return data

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            "controller": ControllerSubentryFlowHandler,
            "accessory": AccessorySubentryFlowHandler,
        }


class ControllerSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow."""

    _bind_task: asyncio.Task | None = None
    _bind_result: BindingStatus | None = None
    _bind_product_id: ProductId
    _bind_product_serial: int | None
    _modbus_address: int | None
    _name: str | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Bind a new controller."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._bind_product_serial = user_input.get(CONF_RF_ADDRESS)
            self._name = user_input.get(CONF_NAME)
            try:
                product = user_input[CONF_DEVICE]
                product_id = SUPPORTED_UNITS.get(product)
                self._bind_product_id = ProductId(product_id)
            except ValueError:
                errors["base"] = "unexpected_product_id"
            return await self.async_step_do_bind_controller()

        bind_schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_DEVICE): vol.In(SUPPORTED_UNITS.keys()),
                vol.Optional(CONF_RF_ADDRESS): int,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=bind_schema, errors=errors
        )

    async def _do_bind(self) -> None:
        assert self._bind_product_id is not None
        _LOGGER.info(
            "Binding new controller (product_id=%s, product_serial=%s)",
            self._bind_product_id,
            self._bind_product_serial,
        )
        config_entry = self._get_entry()
        coordinator: AiriosDataUpdateCoordinator = config_entry.runtime_data
        api = coordinator.api

        _LOGGER.debug("Searching first unassigned Modbus address")
        nodes = await api.nodes()
        addrs = list(range(2, 200))
        for n in nodes:
            addrs.remove(n.slave_id)
        modbus_address = addrs[0]

        _LOGGER.info(
            "Initiating controller binding (Modbus address: %s)", modbus_address
        )
        if not await api.bind_controller(
            modbus_address, self._bind_product_id, self._bind_product_serial
        ):
            raise AiriosBindingException("Failed to send bind command")
        status = BindingStatus.NOT_AVAILABLE
        # Bridge timeout is 20 seconds
        for _ in range(1, 100):
            await asyncio.sleep(0.250)
            status = await api.bind_status()
            _LOGGER.debug("Binding status: %s", str(status))
            if status != BindingStatus.OUTGOING_BINDING_INITIALIZED:
                break
        if status != BindingStatus.OUTGOING_BINDING_COMPLETED:
            # Unbind to remove the virtual Modbus device from the bridge
            await api.unbind(modbus_address)
            self._bind_result = status
            raise AiriosBindingException(f"Bind failed: {status}")
        self._modbus_address = modbus_address
        self._bind_result = status

    async def async_step_do_bind_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Perform the controller binding while showing a progress form."""

        if self._bind_task is None:
            self._bind_task = self.hass.async_create_task(
                self._do_bind(), eager_start=False
            )

        if not self._bind_task.done():
            return self.async_show_progress(
                step_id="do_bind_controller",
                progress_action="bind_controller",
                progress_task=self._bind_task,
            )

        try:
            await self._bind_task
        except AiriosException as err:
            _LOGGER.error("Bind failed: %s", err)
            return self.async_show_progress_done(next_step_id="bind_failed")
        finally:
            self._bind_task = None

        return self.async_show_progress_done(next_step_id="bind_done")

    async def async_step_bind_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Bind failed."""
        if self._bind_result is not None:
            reason = str(self._bind_result)
        else:
            reason = "bind_failed"
        return self.async_abort(reason=reason)

    async def async_step_bind_done(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show the result of the bind step."""
        assert self._bind_result is not None
        assert self._bind_result == BindingStatus.OUTGOING_BINDING_COMPLETED
        assert self._modbus_address is not None

        config_entry = self._get_entry()
        coordinator: AiriosDataUpdateCoordinator = config_entry.runtime_data
        api = coordinator.api
        node = await api.node(self._modbus_address)
        result = await node.node_rf_address()
        assert result is not None
        assert result.value is not None
        rf_address = result.value

        return self.async_create_entry(
            data={
                CONF_NAME: self._name,
                CONF_ADDRESS: self._modbus_address,
                CONF_DEVICE: self._bind_product_id,
                CONF_RF_ADDRESS: rf_address,
            },
            title=self._name,
        )


class AccessorySubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow."""

    _bind_task: asyncio.Task | None = None
    _bind_result: BindingStatus | None = None
    _bind_controller_modbus_address: int
    _bind_product_id: ProductId
    _modbus_address: int | None
    _name: str | None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Bind a new remote or sensor."""

        def _show_form(bound_controllers, errors) -> SubentryFlowResult:
            bind_schema = vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_ADDRESS): vol.In(bound_controllers),
                    vol.Required(CONF_DEVICE): vol.In(SUPPORTED_ACCESSORIES.keys()),
                }
            )
            return self.async_show_form(
                step_id="user", data_schema=bind_schema, errors=errors
            )

        errors: dict[str, str] = {}
        config_entry = self._get_entry()
        bound_controllers = {
            subentry.data[CONF_ADDRESS]: subentry.data[CONF_NAME]
            for subentry in config_entry.subentries.values()
            if subentry.subentry_type == "controller"
        }
        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._bind_controller_modbus_address = user_input[CONF_ADDRESS]
            try:
                product = user_input[CONF_DEVICE]
                product_id = SUPPORTED_ACCESSORIES.get(product)
                self._bind_product_id = ProductId(product_id)
            except ValueError:
                errors["base"] = "unexpected_product_id"
                return _show_form(bound_controllers, errors)
            return await self.async_step_do_bind_accessory()
        return _show_form(bound_controllers, errors)

    async def _do_bind(self) -> None:
        assert self._bind_product_id is not None
        _LOGGER.info(
            "Binding new accessory (controller Modbus address: %s, product ID: %s)",
            self._bind_controller_modbus_address,
            self._bind_product_id,
        )
        config_entry = self._get_entry()
        coordinator: AiriosDataUpdateCoordinator = config_entry.runtime_data
        api = coordinator.api

        _LOGGER.debug("Searching first unassigned Modbus address")
        nodes = await api.nodes()
        addrs = list(range(2, 200))
        for n in nodes:
            addrs.remove(n.slave_id)
        modbus_address = addrs[0]

        _LOGGER.info(
            "Initiating accessory binding (Modbus address: %s)", modbus_address
        )
        if not await api.bind_accessory(
            self._bind_controller_modbus_address,
            modbus_address,
            self._bind_product_id,
        ):
            raise AiriosBindingException("Failed to send bind command")
        status = BindingStatus.NOT_AVAILABLE
        # Bridge timeout is 120 seconds
        for _ in range(1, 500):
            await asyncio.sleep(0.250)
            status = await api.bind_status()
            _LOGGER.debug("Binding status: %s", str(status))
            if status != BindingStatus.INCOMING_BINDING_ACTIVE:
                break
        if status != BindingStatus.INCOMING_BINDING_COMPLETED:
            # Unbind to remove the virtual Modbus device from the bridge
            await api.unbind(modbus_address)
            self._bind_result = status
            raise AiriosBindingException(f"Bind failed: {status}")
        self._modbus_address = modbus_address
        self._bind_result = status

    async def async_step_do_bind_accessory(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Perform the accessory binding while showing a progress form."""

        if self._bind_task is None:
            self._bind_task = self.hass.async_create_task(
                self._do_bind(), eager_start=False
            )

        if not self._bind_task.done():
            return self.async_show_progress(
                step_id="do_bind_accessory",
                progress_action="bind_accessory",
                progress_task=self._bind_task,
            )
        try:
            await self._bind_task
        except AiriosException as err:
            _LOGGER.error("Bind failed: %s", err)
            return self.async_show_progress_done(next_step_id="bind_failed")
        finally:
            self._bind_task = None

        return self.async_show_progress_done(next_step_id="bind_done")

    async def async_step_bind_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Bind failed."""
        if self._bind_result is not None:
            reason = str(self._bind_result)
        else:
            reason = "bind_failed"
        return self.async_abort(reason=reason)

    async def async_step_bind_done(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show the result of the bind step."""
        assert self._bind_result is not None
        assert self._bind_result == BindingStatus.INCOMING_BINDING_COMPLETED
        assert self._modbus_address is not None

        config_entry = self._get_entry()
        coordinator: AiriosDataUpdateCoordinator = config_entry.runtime_data
        api = coordinator.api
        node = await api.node(self._modbus_address)
        result = await node.node_rf_address()
        assert result is not None
        assert result.value is not None
        rf_address = result.value

        return self.async_create_entry(
            data={
                CONF_NAME: self._name,
                CONF_ADDRESS: self._modbus_address,
                CONF_DEVICE: self._bind_product_id,
                CONF_RF_ADDRESS: rf_address,
            },
            title=self._name,
        )


class UnexpectedProductId(HomeAssistantError):
    """Error to indicate unexpected product ID."""
