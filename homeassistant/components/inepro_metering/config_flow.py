"""Config flow for Inepro Metering."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .bluetooth import (
    DiscoveredGrowBluetoothMeter,
    async_discover_grow_bluetooth_meters,
    async_discover_grow_bluetooth_proxy_meters,
    async_entry_data_with_ha_ble_device,
    grow_bluetooth_meter_from_service_info,
)
from .config_flow_create_discovery import CreateDiscoveryFlowMixin
from .config_flow_create_manual import CreateManualFlowMixin
from .config_flow_options_update import OptionsUpdateFlowMixin
from .config_flow_serial_bus import SerialBusFlowMixin
from .config_flow_shared import (
    CONF_ACTION as SHARED_CONF_ACTION,
    CONF_DISCOVERED_BLUETOOTH_METER as SHARED_CONF_DISCOVERED_BLUETOOTH_METER,
    CONF_DISCOVERED_METERS as SHARED_CONF_DISCOVERED_METERS,
    CONF_SELECTED_METER as SHARED_CONF_SELECTED_METER,
    CONF_SELECTED_ROUTE as SHARED_CONF_SELECTED_ROUTE,
    CONFIG_ENTRY_VERSION,
    OPTION_ACTION_ADD_ROUTE as SHARED_OPTION_ACTION_ADD_ROUTE,
    OPTION_ACTION_EDIT_SERIAL_BUS as SHARED_OPTION_ACTION_EDIT_SERIAL_BUS,
    OPTION_ACTION_MANAGE_METER_ROUTES as SHARED_OPTION_ACTION_MANAGE_METER_ROUTES,
    OPTION_ACTION_SCAN_SERIAL as SHARED_OPTION_ACTION_SCAN_SERIAL,
    OPTION_ACTION_SWITCH_ROUTE as SHARED_OPTION_ACTION_SWITCH_ROUTE,
    OPTION_ACTION_UPDATE_CONNECTION as SHARED_OPTION_ACTION_UPDATE_CONNECTION,
    OPTION_ACTION_UPDATE_POLLING as SHARED_OPTION_ACTION_UPDATE_POLLING,
    IneproIdentityError as SharedIneproIdentityError,
    async_read_detected_grow_serial as shared_read_detected_serial,
    async_resolve_entry_serial_number_for_creation as shared_resolve_entry_serial,
    async_validate_bluetooth_gatt_identity as shared_validate_bluetooth_gatt_identity,
    async_validate_entry_identity as shared_validate_entry_identity,
    bluetooth_meter_key,
    build_unique_id,
    configured_entry_serial_number,
    configured_grow_serial,
    discovered_meter_key,
    meter_slave_id_field,
    normalize_connection_data,
    user_value,
)
from .const import (
    CONF_FAMILY,
    CONF_METERS,
    CONF_SERIAL_NUMBER,
    CONF_SLAVE_ID,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DOMAIN,
    TransportType,
)
from .discovery import (
    DiscoveredGrowMeter,
    DiscoveredTcpGateway,
    async_discover_grow_serial_bus,
    async_discover_grow_tcp_gateway,
    async_discover_tcp_gateways,
)
from .modbus import IneproModbusClient, async_validate_modbus_config

_LOGGER = logging.getLogger(__name__)

_configured_entry_serial_number = configured_entry_serial_number
_configured_grow_serial = configured_grow_serial
CONF_ACTION = SHARED_CONF_ACTION
CONF_DISCOVERED_BLUETOOTH_METER = SHARED_CONF_DISCOVERED_BLUETOOTH_METER
CONF_DISCOVERED_METERS = SHARED_CONF_DISCOVERED_METERS
CONF_SELECTED_METER = SHARED_CONF_SELECTED_METER
CONF_SELECTED_ROUTE = SHARED_CONF_SELECTED_ROUTE
OPTION_ACTION_EDIT_SERIAL_BUS = SHARED_OPTION_ACTION_EDIT_SERIAL_BUS
OPTION_ACTION_ADD_ROUTE = SHARED_OPTION_ACTION_ADD_ROUTE
OPTION_ACTION_MANAGE_METER_ROUTES = SHARED_OPTION_ACTION_MANAGE_METER_ROUTES
OPTION_ACTION_SCAN_SERIAL = SHARED_OPTION_ACTION_SCAN_SERIAL
OPTION_ACTION_SWITCH_ROUTE = SHARED_OPTION_ACTION_SWITCH_ROUTE
OPTION_ACTION_UPDATE_CONNECTION = SHARED_OPTION_ACTION_UPDATE_CONNECTION
OPTION_ACTION_UPDATE_POLLING = SHARED_OPTION_ACTION_UPDATE_POLLING
IneproIdentityError = SharedIneproIdentityError
_normalize_connection_data = normalize_connection_data
_build_unique_id = build_unique_id
_user_value = user_value
_discovered_meter_key = discovered_meter_key
_bluetooth_meter_key = bluetooth_meter_key
_meter_slave_id_field = meter_slave_id_field
async_validate_bluetooth_gatt_identity = shared_validate_bluetooth_gatt_identity


async def _async_read_detected_grow_serial(
    entry_data: dict[str, Any],
    *,
    product_code: str | None = None,
) -> str | None:
    """Read the live GROW serial number directly from the meter."""
    return await shared_read_detected_serial(
        entry_data,
        product_code=product_code,
        modbus_client_factory=IneproModbusClient,
    )


async def _async_resolve_entry_serial_number_for_creation(
    entry_data: dict[str, Any],
) -> str | None:
    """Resolve the serial number to persist for a new config entry."""
    return await shared_resolve_entry_serial(
        entry_data,
        read_detected_grow_serial=_async_read_detected_grow_serial,
    )


async def _async_validate_entry_identity(entry_data: dict[str, Any]) -> None:
    """Confirm that a re-targeted entry still points at the same GROW meter."""
    await shared_validate_entry_identity(
        entry_data,
        read_detected_grow_serial=_async_read_detected_grow_serial,
    )


class _ConfigFlowDependencyBridge:
    """Bridge extracted mixins back to patchable config_flow module globals."""

    def _runtime_entry_data_for_validation(
        self, entry_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return entry data with temporary runtime-only validation objects."""
        return async_entry_data_with_ha_ble_device(self.hass, entry_data)

    async def _async_validate_modbus_config(self, entry_data: dict[str, Any]) -> None:
        """Validate one connection using the patchable module helper."""
        await async_validate_modbus_config(
            self._runtime_entry_data_for_validation(entry_data)
        )

    async def _async_validate_bluetooth_gatt_identity(
        self,
        entry_data: dict[str, Any],
    ) -> str | None:
        """Validate direct GROW BLE Device Information before Modbus traffic."""
        return await async_validate_bluetooth_gatt_identity(
            async_entry_data_with_ha_ble_device(
                self.hass,
                entry_data,
                pairing_mode=None,
            )
        )

    async def _async_resolve_entry_serial_number_for_creation(
        self,
        entry_data: dict[str, Any],
    ) -> str | None:
        """Resolve the serial number using the patchable module helper."""
        return await _async_resolve_entry_serial_number_for_creation(
            self._runtime_entry_data_for_validation(entry_data)
        )

    async def _async_validate_entry_identity(self, entry_data: dict[str, Any]) -> None:
        """Validate identity using the patchable module helper."""
        await _async_validate_entry_identity(
            self._runtime_entry_data_for_validation(entry_data)
        )

    async def _async_discover_grow_serial_bus(
        self,
        connection_data: dict[str, Any],
        *,
        slave_id_start: int,
        slave_id_end: int,
    ) -> tuple[DiscoveredGrowMeter, ...]:
        """Discover GROW meters on one serial bus."""
        return await async_discover_grow_serial_bus(
            connection_data,
            slave_id_start=slave_id_start,
            slave_id_end=slave_id_end,
        )

    async def _async_discover_grow_tcp_gateway(
        self,
        connection_data: dict[str, Any],
        *,
        slave_id_start: int,
        slave_id_end: int,
    ) -> tuple[DiscoveredGrowMeter, ...]:
        """Discover GROW meters through one Modbus TCP gateway."""
        return await async_discover_grow_tcp_gateway(
            connection_data,
            slave_id_start=slave_id_start,
            slave_id_end=slave_id_end,
        )

    async def _async_discover_tcp_gateways(
        self,
        *,
        scan_target: str | None = None,
    ) -> tuple[DiscoveredTcpGateway, ...]:
        """Discover TCP gateways on the local network."""
        return await async_discover_tcp_gateways(scan_target=scan_target)

    def _async_discover_grow_bluetooth_meters(
        self,
    ) -> tuple[DiscoveredGrowBluetoothMeter, ...]:
        """Read GROW Bluetooth discoveries from Home Assistant."""
        return async_discover_grow_bluetooth_meters(self.hass)

    async def _async_discover_grow_bluetooth_proxy_meters(
        self,
    ) -> tuple[DiscoveredGrowBluetoothMeter, ...]:
        """Read GROW Bluetooth discoveries from the Windows BLE proxy."""
        return await async_discover_grow_bluetooth_proxy_meters()

    def _grow_bluetooth_meter_from_service_info(self, discovery_info):
        """Convert Home Assistant Bluetooth discovery info into a meter model."""
        return grow_bluetooth_meter_from_service_info(discovery_info)


class IneproMeteringConfigFlow(
    OptionsUpdateFlowMixin,
    CreateDiscoveryFlowMixin,
    CreateManualFlowMixin,
    SerialBusFlowMixin,
    _ConfigFlowDependencyBridge,
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for Inepro Metering."""

    VERSION = CONFIG_ENTRY_VERSION

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow handler for this config entry."""
        return IneproMeteringOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config_entry: ConfigEntry | None = None
        self._meter_selection: dict[str, Any] = {}
        self._discovered_bluetooth_devices: tuple[
            DiscoveredGrowBluetoothMeter, ...
        ] = ()
        self._discovered_bus_devices: tuple[DiscoveredGrowMeter, ...] = ()
        self._discovered_gateways: tuple[DiscoveredTcpGateway, ...] = ()
        self._bus_scan_connection: dict[str, Any] = {}
        self._bus_scan_defaults: dict[str, Any] = {}
        self._gateway_scan_form_defaults: dict[str, Any] = {}
        self._bus_scan_transport: TransportType | None = None
        self._route_selection: dict[str, Any] = {}
        self._selected_meter_key: str | None = None
        self._zeroconf_discovery: dict[str, Any] = {}

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Update one existing entry without removing and recreating it."""
        del user_input
        self._config_entry = self._get_reconfigure_entry()
        if self._config_entry.unique_id is not None:
            await self.async_set_unique_id(self._config_entry.unique_id)
            self._abort_if_unique_id_mismatch()

        if CONF_METERS in self._config_entry.data:
            return await self.async_step_edit_serial_bus()

        self._meter_selection = {
            CONF_FAMILY: str(self._config_entry.data[CONF_FAMILY]),
            CONF_NAME: str(
                self._config_entry.data.get(CONF_NAME, self._config_entry.title)
            ),
            CONF_VARIANT: str(self._config_entry.data[CONF_VARIANT]),
            CONF_SLAVE_ID: int(self._config_entry.data[CONF_SLAVE_ID]),
            CONF_SCAN_INTERVAL: int(self._config_entry.data[CONF_SCAN_INTERVAL]),
            CONF_TRANSPORT: str(self._config_entry.data[CONF_TRANSPORT]),
        }
        if self._config_entry.data.get(CONF_SERIAL_NUMBER) is not None:
            self._meter_selection[CONF_SERIAL_NUMBER] = str(
                self._config_entry.data[CONF_SERIAL_NUMBER]
            )

        if len(self._available_transports_for_current_flow) > 1:
            return await self.async_step_transport()

        self._meter_selection[CONF_TRANSPORT] = (
            self._available_transports_for_current_flow[0].value
        )
        return await self.async_step_connection()


class IneproMeteringOptionsFlow(
    OptionsUpdateFlowMixin,
    SerialBusFlowMixin,
    _ConfigFlowDependencyBridge,
    config_entries.OptionsFlow,
):
    """Handle options for Inepro Metering entries."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry
        self._discovered_bluetooth_devices: tuple[
            DiscoveredGrowBluetoothMeter, ...
        ] = ()
        self._discovered_bus_devices: tuple[DiscoveredGrowMeter, ...] = ()
        self._bus_scan_defaults: dict[str, Any] = {}
        self._bus_scan_transport: TransportType | None = None
        self._route_selection: dict[str, Any] = {}
        self._selected_meter_key: str | None = None
