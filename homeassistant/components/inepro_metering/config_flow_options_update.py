"""Options/update workflow steps for the Inepro Metering config flow."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
)
from homeassistant.data_entry_flow import FlowResult

from .bluetooth import IneproBluetoothDeviceNotFound
from .config_flow_schemas import (
    build_action_schema,
    build_add_route_bluetooth_discovered_schema,
    build_add_route_connection_schema,
    build_add_route_purpose_schema,
    build_add_route_schema,
    build_discovered_serial_schema,
    build_edit_serial_bus_schema,
    build_select_meter_schema,
    build_serial_bus_scan_schema,
    build_switch_route_schema,
    build_update_connection_schema,
    build_update_polling_schema,
)
from .config_flow_shared import (
    CONF_ACTION,
    CONF_DISCOVERED_BLUETOOTH_METER,
    CONF_DISCOVERED_METERS,
    CONF_SELECTED_METER,
    CONF_SELECTED_ROUTE,
    CONFIG_ENTRY_VERSION,
    OPTION_ACTION_ADD_ROUTE,
    OPTION_ACTION_EDIT_SERIAL_BUS,
    OPTION_ACTION_MANAGE_METER_ROUTES,
    OPTION_ACTION_SCAN_SERIAL,
    OPTION_ACTION_SWITCH_ROUTE,
    OPTION_ACTION_UPDATE_CONNECTION,
    OPTION_ACTION_UPDATE_POLLING,
    IneproIdentityError,
    bluetooth_gatt_validation_data,
    bluetooth_meter_key,
    bluetooth_modbus_pairing_validation_data,
    bluetooth_validation_error_reason,
    configured_entry_serial_number,
    connection_error_reason,
    meter_slave_id_field,
    normalize_connection_data,
    user_visible_transports,
)
from .const import (
    CONF_ACTIVE_ROUTE,
    CONF_BAUDRATE,
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_BYTESIZE,
    CONF_FAMILY,
    CONF_METERS,
    CONF_PARITY,
    CONF_ROUTE_PURPOSE,
    CONF_ROUTES,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DEFAULT_SCAN_INTERVAL,
    ROUTE_PURPOSE_ACTIVE,
    TransportType,
)
from .discovery import CONF_SLAVE_ID_END, CONF_SLAVE_ID_START
from .entry_data import (
    ConfiguredMeter,
    ConfiguredRoute,
    build_meter_key,
    build_route_from_entry_data,
    build_route_key,
    ensure_bus_meter_routes,
    get_active_route,
    get_active_route_for_meter,
    get_bus_route_for_meter,
    get_configured_routes,
    get_meter_routes,
    normalize_entry_route_data,
    route_matches_connection,
    serialize_configured_meter,
    with_meter_routes,
    with_routes_applied,
)
from .modbus import IneproConnectionError
from .models import get_profile


class OptionsUpdateFlowMixin:
    """Options/update steps for existing Inepro Metering entries."""

    async def _async_finish_entry_update(
        self,
        *,
        data: dict[str, Any],
        title: str | None = None,
        version: int | None = None,
    ) -> FlowResult:
        """Persist one updated entry for either options or reconfigure flows."""
        data = normalize_entry_route_data(
            data,
            title=self._config_entry.title,
        )
        if getattr(self, "source", None) == SOURCE_RECONFIGURE:
            if version is not None and version != self._config_entry.version:
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    version=version,
                )
            return self.async_update_reload_and_abort(
                self._config_entry,
                unique_id=self._config_entry.unique_id,
                title=self._config_entry.title if title is None else title,
                data=data,
            )

        update_kwargs: dict[str, Any] = {"data": data}
        if title is not None:
            update_kwargs["title"] = title
        if version is not None:
            update_kwargs["version"] = version
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            **update_kwargs,
        )
        await self.hass.config_entries.async_reload(self._config_entry.entry_id)
        return self.async_create_entry(title="", data={})

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose how to update an existing entry."""
        if (
            user_input is None
            and not (
                self._supports_serial_rescan
                or self._supports_route_management
                or self._supports_bus_meter_route_management
            )
            and self._supports_connection_update
        ):
            return await self.async_step_update_connection()

        if user_input is not None:
            if user_input[CONF_ACTION] == OPTION_ACTION_EDIT_SERIAL_BUS:
                return await self.async_step_edit_serial_bus()
            if user_input[CONF_ACTION] == OPTION_ACTION_SCAN_SERIAL:
                return await self.async_step_serial_bus_scan()
            if user_input[CONF_ACTION] == OPTION_ACTION_MANAGE_METER_ROUTES:
                return await self.async_step_select_meter()
            if user_input[CONF_ACTION] == OPTION_ACTION_ADD_ROUTE:
                return await self.async_step_add_route()
            if user_input[CONF_ACTION] == OPTION_ACTION_SWITCH_ROUTE:
                return await self.async_step_switch_route()
            if user_input[CONF_ACTION] == OPTION_ACTION_UPDATE_CONNECTION:
                if self._supports_serial_rescan:
                    return await self.async_step_edit_serial_bus()
                return await self.async_step_update_connection()
            return await self.async_step_update_polling()

        return self.async_show_form(
            step_id="init",
            data_schema=build_action_schema(self._action_options, self._default_action),
        )

    async def async_step_select_meter(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose which shared-bus meter should manage routes."""
        if user_input is not None:
            self._selected_meter_key = str(user_input[CONF_SELECTED_METER])
            return await self.async_step_manage_meter_routes()

        return self.async_show_form(
            step_id="select_meter",
            data_schema=build_select_meter_schema(
                self._bus_meter_options,
                self._selected_meter_key or self._bus_meter_options[0]["value"],
            ),
        )

    async def async_step_manage_meter_routes(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose how to manage routes for the selected shared-bus meter."""
        if user_input is not None:
            if user_input[CONF_ACTION] == OPTION_ACTION_ADD_ROUTE:
                return await self.async_step_add_route()
            if user_input[CONF_ACTION] == OPTION_ACTION_SWITCH_ROUTE:
                return await self.async_step_switch_route()
            return await self.async_step_update_connection()

        return self.async_show_form(
            step_id="manage_meter_routes",
            data_schema=build_action_schema(
                self._meter_route_action_options,
                OPTION_ACTION_UPDATE_CONNECTION,
            ),
            description_placeholders={
                "meter": self._selected_meter.name
                if self._selected_meter is not None
                else "",
            },
        )

    async def async_step_edit_serial_bus(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Edit one shared Modbus bus and the meter addresses on that bus."""
        if user_input is not None:
            transport = TransportType(self._config_entry.data[CONF_TRANSPORT])
            updated_bus_data = {
                **self._config_entry.data,
                CONF_TRANSPORT: transport.value,
                CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
            }
            if transport is TransportType.SERIAL:
                updated_bus_data.update(
                    {
                        CONF_SERIAL_PORT: str(user_input[CONF_SERIAL_PORT]).strip(),
                        CONF_BAUDRATE: int(user_input[CONF_BAUDRATE]),
                        CONF_BYTESIZE: int(user_input[CONF_BYTESIZE]),
                        CONF_PARITY: str(user_input[CONF_PARITY]),
                        CONF_STOPBITS: int(user_input[CONF_STOPBITS]),
                    }
                )
            else:
                updated_bus_data.update(
                    {
                        CONF_HOST: str(user_input[CONF_HOST]).strip(),
                        CONF_PORT: int(user_input[CONF_PORT]),
                    }
                )
            meters = []
            for meter in self._configured_meters:
                bus_route = get_bus_route_for_meter(
                    meter,
                    bus_entry_data=self._config_entry.data,
                )
                if transport is TransportType.SERIAL:
                    updated_bus_route = ConfiguredRoute(
                        transport=TransportType.SERIAL,
                        slave_id=int(user_input[meter_slave_id_field(meter)]),
                        timeout=int(user_input[CONF_TIMEOUT]),
                        purpose=bus_route.purpose,
                        serial_port=str(user_input[CONF_SERIAL_PORT]).strip(),
                        baudrate=int(user_input[CONF_BAUDRATE]),
                        bytesize=int(user_input[CONF_BYTESIZE]),
                        parity=str(user_input[CONF_PARITY]),
                        stopbits=int(user_input[CONF_STOPBITS]),
                    )
                else:
                    updated_bus_route = ConfiguredRoute(
                        transport=TransportType.TCP_GATEWAY,
                        slave_id=int(user_input[meter_slave_id_field(meter)]),
                        timeout=int(user_input[CONF_TIMEOUT]),
                        purpose=bus_route.purpose,
                        host=str(user_input[CONF_HOST]).strip(),
                        port=int(user_input[CONF_PORT]),
                    )
                updated_routes = tuple(
                    updated_bus_route
                    if route_matches_connection(route, self._config_entry.data)
                    else route
                    for route in get_meter_routes(
                        meter,
                        bus_entry_data=self._config_entry.data,
                    )
                )
                meters.append(
                    ensure_bus_meter_routes(
                        with_meter_routes(
                            meter,
                            updated_routes,
                            active_route_key=(
                                build_route_key(updated_bus_route)
                                if meter.active_route == build_route_key(bus_route)
                                else meter.active_route
                            ),
                        ),
                        bus_entry_data=updated_bus_data,
                    )
                )
            return await self._async_finish_entry_update(
                title=str(user_input[CONF_NAME]).strip() or self._config_entry.title,
                data={
                    **updated_bus_data,
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_METERS: [
                        serialize_configured_meter(meter) for meter in meters
                    ],
                },
                version=CONFIG_ENTRY_VERSION,
            )

        return self.async_show_form(
            step_id="edit_serial_bus",
            data_schema=build_edit_serial_bus_schema(
                self._config_entry.data,
                self._config_entry.title,
                self._configured_meters,
                user_input,
            ),
            description_placeholders={
                "count": str(len(self._configured_meters)),
                "bus_type": (
                    "serial Modbus RTU bus"
                    if TransportType(self._config_entry.data[CONF_TRANSPORT])
                    is TransportType.SERIAL
                    else "Modbus TCP gateway bus"
                ),
            },
        )

    async def async_step_update_polling(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Update the polling interval for the current entry."""
        if user_input is not None:
            return await self._async_finish_entry_update(
                data={
                    **self._config_entry.data,
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        return self.async_show_form(
            step_id="update_polling",
            data_schema=build_update_polling_schema(
                int(
                    self._config_entry.data.get(
                        CONF_SCAN_INTERVAL,
                        DEFAULT_SCAN_INTERVAL,
                    )
                )
            ),
        )

    async def async_step_update_connection(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Update the currently active transport route for the current entry."""
        errors: dict[str, str] = {}
        transport = self._active_route.transport
        current_route_key = build_route_key(self._active_route)

        if user_input is not None:
            connection_data = normalize_connection_data(transport, user_input)
            updated_data = self._candidate_entry_data_for_route(
                transport=transport,
                connection_data=connection_data,
                slave_id=int(user_input[CONF_SLAVE_ID]),
                scan_interval=int(user_input[CONF_SCAN_INTERVAL]),
            )
            route_validation_data = self._route_validation_entry_data(updated_data)
            gatt_validation_data = bluetooth_gatt_validation_data(route_validation_data)
            validation_data = bluetooth_modbus_pairing_validation_data(
                route_validation_data
            )

            gatt_validated = False
            modbus_validated = False
            try:
                await self._async_validate_bluetooth_gatt_identity(gatt_validation_data)
                gatt_validated = True
                if transport is not TransportType.BLUETOOTH:
                    await self._async_validate_modbus_config(validation_data)
                modbus_validated = True
                await self._async_validate_entry_identity(validation_data)
            except IneproBluetoothDeviceNotFound:
                errors["base"] = "bluetooth_device_not_found"
            except IneproConnectionError as err:
                errors["base"] = (
                    bluetooth_validation_error_reason(err, transport)
                    if transport is TransportType.BLUETOOTH
                    and (not gatt_validated or modbus_validated)
                    else connection_error_reason(err, transport)
                )
            except IneproIdentityError:
                errors["base"] = "invalid_identity"
            else:
                updated_route = build_route_from_entry_data(
                    updated_data,
                    purpose=ROUTE_PURPOSE_ACTIVE,
                )
                updated_routes = tuple(
                    updated_route
                    if build_route_key(route) == current_route_key
                    else route
                    for route in self._configured_routes
                )
                new_data = self._apply_routes_to_entry(
                    updated_data=updated_data,
                    routes=updated_routes,
                    active_route_key=build_route_key(updated_route),
                )
                return await self._async_finish_entry_update(
                    data=new_data,
                )

        return self.async_show_form(
            step_id="update_connection",
            data_schema=build_update_connection_schema(
                self._update_connection_defaults,
                user_input,
            ),
            errors=errors,
        )

    async def async_step_add_route(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose the transport for one additional route."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                TransportType(user_input[CONF_TRANSPORT])
                not in self._supported_route_transports
            ):
                errors["base"] = "transport_required"
                return self.async_show_form(
                    step_id="add_route",
                    data_schema=build_add_route_schema(
                        self._supported_route_transports,
                        user_input,
                    ),
                    errors=errors,
                )
            self._route_selection = {
                CONF_TRANSPORT: user_input[CONF_TRANSPORT],
            }
            transport = TransportType(user_input[CONF_TRANSPORT])
            if self._transport_supports_helper_only_routes(transport):
                return await self.async_step_add_route_purpose()
            self._route_selection[CONF_ROUTE_PURPOSE] = ROUTE_PURPOSE_ACTIVE
            return await self.async_step_add_route_connection()

        return self.async_show_form(
            step_id="add_route",
            data_schema=build_add_route_schema(
                self._supported_route_transports,
                user_input,
            ),
        )

    async def async_step_add_route_purpose(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose whether a helper-capable route should be active or helper-only."""
        if user_input is not None:
            self._route_selection[CONF_ROUTE_PURPOSE] = user_input[CONF_ROUTE_PURPOSE]
            if (
                TransportType(self._route_selection[CONF_TRANSPORT])
                is TransportType.BLUETOOTH
            ):
                return await self.async_step_add_route_bluetooth_scan()
            return await self.async_step_add_route_connection()

        return self.async_show_form(
            step_id="add_route_purpose",
            data_schema=build_add_route_purpose_schema(user_input),
        )

    async def async_step_add_route_bluetooth_scan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Scan Home Assistant's Bluetooth cache before adding a route."""
        self._discovered_bluetooth_devices = (
            self._async_discover_route_bluetooth_meters()
        )
        if self._discovered_bluetooth_devices:
            return await self.async_step_add_route_bluetooth_discovered()

        return self.async_show_form(
            step_id="add_route_bluetooth_scan",
            data_schema=vol.Schema({}),
            errors={"base": "bluetooth_device_not_found"},
            description_placeholders={
                "meter": self._route_meter_display_name,
            },
        )

    async def async_step_add_route_bluetooth_discovered(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose a discovered Bluetooth meter for a new route."""
        errors: dict[str, str] = {}

        if user_input is not None:
            discovered_meter = self._get_discovered_bluetooth_meter(
                str(user_input[CONF_DISCOVERED_BLUETOOTH_METER])
            )
            route_input = {
                **user_input,
                CONF_BLUETOOTH_ADDRESS: discovered_meter.address,
                CONF_BLUETOOTH_NAME: discovered_meter.bluetooth_name,
            }
            result = await self._async_add_route_from_user_input(
                TransportType.BLUETOOTH,
                route_input,
                errors,
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="add_route_bluetooth_discovered",
            data_schema=build_add_route_bluetooth_discovered_schema(
                self._discovered_bluetooth_devices,
                user_input,
            ),
            description_placeholders={
                "count": str(len(self._discovered_bluetooth_devices)),
                "meter": self._route_meter_display_name,
            },
            errors=errors,
        )

    async def async_step_add_route_connection(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Collect connection details for a new route."""
        errors: dict[str, str] = {}
        transport = TransportType(self._route_selection[CONF_TRANSPORT])

        if user_input is not None:
            result = await self._async_add_route_from_user_input(
                transport,
                user_input,
                errors,
            )
            if result is not None:
                return result

        return self.async_show_form(
            step_id="add_route_connection",
            data_schema=build_add_route_connection_schema(transport, user_input),
            errors=errors,
        )

    async def async_step_switch_route(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Switch the active route for one configured physical meter."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_route_key = str(user_input[CONF_SELECTED_ROUTE])
            routes = list(self._configured_routes)
            selected_route = next(
                (
                    route
                    for route in routes
                    if build_route_key(route) == selected_route_key
                ),
                None,
            )
            if selected_route is None:
                errors["base"] = "route_not_found"
            else:
                promoted_route = ConfiguredRoute(
                    transport=selected_route.transport,
                    slave_id=selected_route.slave_id,
                    timeout=selected_route.timeout,
                    purpose=ROUTE_PURPOSE_ACTIVE,
                    host=selected_route.host,
                    port=selected_route.port,
                    serial_port=selected_route.serial_port,
                    baudrate=selected_route.baudrate,
                    bytesize=selected_route.bytesize,
                    parity=selected_route.parity,
                    stopbits=selected_route.stopbits,
                    bluetooth_address=selected_route.bluetooth_address,
                    bluetooth_name=selected_route.bluetooth_name,
                )
                updated_routes = tuple(
                    promoted_route
                    if build_route_key(route) == selected_route_key
                    else route
                    for route in routes
                )
                candidate_data = self._candidate_entry_data_for_route(
                    transport=promoted_route.transport,
                    connection_data=self._connection_data_from_route(promoted_route),
                    slave_id=promoted_route.slave_id,
                    scan_interval=int(self._config_entry.data[CONF_SCAN_INTERVAL]),
                )
                route_validation_data = self._route_validation_entry_data(
                    candidate_data
                )
                gatt_validation_data = bluetooth_gatt_validation_data(
                    route_validation_data
                )
                validation_data = bluetooth_modbus_pairing_validation_data(
                    route_validation_data
                )
                new_data = self._apply_routes_to_entry(
                    updated_data=candidate_data,
                    routes=updated_routes,
                    active_route_key=selected_route_key,
                )
                gatt_validated = False
                modbus_validated = False
                try:
                    await self._async_validate_bluetooth_gatt_identity(
                        gatt_validation_data
                    )
                    gatt_validated = True
                    if promoted_route.transport is not TransportType.BLUETOOTH:
                        await self._async_validate_modbus_config(validation_data)
                    modbus_validated = True
                    await self._async_validate_entry_identity(validation_data)
                except IneproBluetoothDeviceNotFound:
                    errors["base"] = "bluetooth_device_not_found"
                except IneproConnectionError as err:
                    errors["base"] = (
                        bluetooth_validation_error_reason(err, promoted_route.transport)
                        if promoted_route.transport is TransportType.BLUETOOTH
                        and (not gatt_validated or modbus_validated)
                        else connection_error_reason(err, promoted_route.transport)
                    )
                except IneproIdentityError:
                    errors["base"] = "invalid_identity"
                else:
                    return await self._async_finish_entry_update(
                        data=new_data,
                    )

        return self.async_show_form(
            step_id="switch_route",
            data_schema=build_switch_route_schema(
                self._configured_routes,
                self._active_route_key,
            ),
            errors=errors,
        )

    async def async_step_serial_bus_scan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Scan the current shared bus for additional supported meters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if int(user_input[CONF_SLAVE_ID_START]) > int(
                user_input[CONF_SLAVE_ID_END]
            ):
                errors["base"] = "invalid_scan_range"
                return self.async_show_form(
                    step_id="serial_bus_scan",
                    data_schema=build_serial_bus_scan_schema(
                        self._config_entry.data,
                        user_input,
                    ),
                    errors=errors,
                )

            self._bus_scan_defaults = {
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                CONF_SLAVE_ID_START: int(user_input[CONF_SLAVE_ID_START]),
                CONF_SLAVE_ID_END: int(user_input[CONF_SLAVE_ID_END]),
            }

            try:
                if (
                    TransportType(self._config_entry.data[CONF_TRANSPORT])
                    is TransportType.TCP_GATEWAY
                ):
                    discovered = await self._async_discover_grow_tcp_gateway(
                        self._bus_connection_data,
                        slave_id_start=self._bus_scan_defaults[CONF_SLAVE_ID_START],
                        slave_id_end=self._bus_scan_defaults[CONF_SLAVE_ID_END],
                    )
                else:
                    discovered = await self._async_discover_grow_serial_bus(
                        self._bus_connection_data,
                        slave_id_start=self._bus_scan_defaults[CONF_SLAVE_ID_START],
                        slave_id_end=self._bus_scan_defaults[CONF_SLAVE_ID_END],
                    )
            except IneproConnectionError:
                errors["base"] = "cannot_connect"
            else:
                self._discovered_bus_devices = self._filter_new_bus_devices(
                    discovered,
                    connection_data=self._bus_connection_data,
                    transport=TransportType(self._config_entry.data[CONF_TRANSPORT]),
                )
                if not self._discovered_bus_devices:
                    errors["base"] = "no_new_devices_found"
                else:
                    return await self.async_step_serial_bus_discovered()

        return self.async_show_form(
            step_id="serial_bus_scan",
            data_schema=build_serial_bus_scan_schema(
                self._config_entry.data,
                user_input,
            ),
            errors=errors,
            description_placeholders={
                "bus_endpoint": (
                    str(self._config_entry.data[CONF_SERIAL_PORT])
                    if TransportType(self._config_entry.data[CONF_TRANSPORT])
                    is TransportType.SERIAL
                    else f"{self._config_entry.data[CONF_HOST]}:{self._config_entry.data[CONF_PORT]}"
                ),
            },
        )

    async def async_step_serial_bus_discovered(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose which newly found meters to append to the current bus."""
        if user_input is not None:
            selected_meters = self._get_discovered_meters(
                user_input[CONF_DISCOVERED_METERS]
            )
            existing_meters = [
                ensure_bus_meter_routes(
                    meter,
                    bus_entry_data=self._config_entry.data,
                )
                for meter in self._configured_meters
            ]
            merged_meters = [
                *existing_meters,
                *(
                    ensure_bus_meter_routes(
                        ConfiguredMeter(
                            family=discovered_meter.family.value,
                            name=discovered_meter.serial_number,
                            variant=discovered_meter.variant,
                            slave_id=discovered_meter.slave_id,
                            serial_number=discovered_meter.serial_number,
                            product_code=discovered_meter.product_code,
                        ),
                        bus_entry_data=self._config_entry.data,
                    )
                    for discovered_meter in selected_meters
                ),
            ]
            return await self._async_finish_entry_update(
                data={
                    **self._config_entry.data,
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_METERS: [
                        serialize_configured_meter(meter) for meter in merged_meters
                    ],
                },
                version=CONFIG_ENTRY_VERSION,
            )

        return self.async_show_form(
            step_id="serial_bus_discovered",
            data_schema=build_discovered_serial_schema(
                self._discovered_bus_devices,
                scan_interval_default=self._bus_scan_defaults.get(
                    CONF_SCAN_INTERVAL,
                    int(
                        self._config_entry.data.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL,
                        )
                    ),
                ),
            ),
            description_placeholders={
                "count": str(len(self._discovered_bus_devices)),
            },
        )

    @property
    def _default_action(self) -> str:
        """Return the best default option for the current entry type."""
        if self._supports_serial_rescan:
            return OPTION_ACTION_EDIT_SERIAL_BUS
        if self._supports_bus_meter_route_management:
            return OPTION_ACTION_MANAGE_METER_ROUTES
        if self._supports_route_management:
            return OPTION_ACTION_UPDATE_CONNECTION
        if self._supports_connection_update:
            return OPTION_ACTION_UPDATE_CONNECTION
        return OPTION_ACTION_UPDATE_POLLING

    @property
    def _action_options(self) -> list[dict[str, str]]:
        """Return the available options actions for the current entry."""
        options: list[dict[str, str]] = []
        if self._supports_serial_rescan:
            bus_transport = TransportType(self._config_entry.data[CONF_TRANSPORT])
            bus_label = (
                "shared Modbus RTU bus"
                if bus_transport is TransportType.SERIAL
                else "Modbus TCP gateway bus"
            )
            options.append(
                {
                    "value": OPTION_ACTION_EDIT_SERIAL_BUS,
                    "label": f"Edit {bus_label} and meter Modbus IDs",
                }
            )
            options.append(
                {
                    "value": OPTION_ACTION_SCAN_SERIAL,
                    "label": f"Scan this {bus_label} for additional meters",
                }
            )
            options.append(
                {
                    "value": OPTION_ACTION_MANAGE_METER_ROUTES,
                    "label": "Manage routes for one meter on this entry",
                }
            )
        if self._supports_route_management:
            options.append(
                {
                    "value": OPTION_ACTION_UPDATE_CONNECTION,
                    "label": "Update active route",
                }
            )
            options.append(
                {
                    "value": OPTION_ACTION_ADD_ROUTE,
                    "label": "Add another route",
                }
            )
            options.append(
                {
                    "value": OPTION_ACTION_SWITCH_ROUTE,
                    "label": "Switch active route",
                }
            )
        elif self._supports_connection_update and not self._supports_serial_rescan:
            options.append(
                {
                    "value": OPTION_ACTION_UPDATE_CONNECTION,
                    "label": "Update connection details",
                }
            )
        options.append(
            {
                "value": OPTION_ACTION_UPDATE_POLLING,
                "label": "Update polling interval only",
            }
        )
        return options

    @property
    def _supports_serial_rescan(self) -> bool:
        """Return whether the current entry supports shared-bus rescans."""
        return (
            TransportType(self._config_entry.data[CONF_TRANSPORT])
            in {TransportType.SERIAL, TransportType.TCP_GATEWAY}
            and CONF_METERS in self._config_entry.data
        )

    @property
    def _supports_connection_update(self) -> bool:
        """Return whether this entry can update transport connection settings."""
        return TransportType(self._config_entry.data[CONF_TRANSPORT]) in {
            TransportType.SERIAL,
            TransportType.TCP_GATEWAY,
            TransportType.TCP_ETHERNET,
            TransportType.TCP_WIFI,
            TransportType.BLUETOOTH,
            TransportType.BLUETOOTH_PROXY,
        }

    @property
    def _supports_bus_meter_route_management(self) -> bool:
        """Return whether this shared-bus entry can manage per-meter routes."""
        return self._supports_serial_rescan and bool(self._configured_meters)

    @property
    def _supports_route_management(self) -> bool:
        """Return whether this entry can manage multiple per-meter routes."""
        return (
            CONF_METERS not in self._config_entry.data
            and len(self._supported_route_transports) > 1
        )

    @property
    def _supported_route_transports(self) -> tuple[TransportType, ...]:
        """Return supported transports for the currently managed meter."""
        if self._selected_meter is not None:
            profile = get_profile(
                self._selected_meter.family,
                self._selected_meter.variant,
            )
            return user_visible_transports(profile.supported_transports)

        profile = get_profile(
            self._config_entry.data[CONF_FAMILY],
            self._config_entry.data[CONF_VARIANT],
        )
        return user_visible_transports(profile.supported_transports)

    @property
    def _configured_routes(self):
        """Return configured routes for the current meter context."""
        if self._selected_meter is not None:
            return get_meter_routes(
                self._selected_meter,
                bus_entry_data=self._config_entry.data,
            )
        return get_configured_routes(self._config_entry.data)

    @property
    def _active_route_key(self) -> str | None:
        """Return the stored active-route key for the current meter context."""
        if self._selected_meter is not None:
            return self._selected_meter.active_route
        active_route_key = self._config_entry.data.get(CONF_ACTIVE_ROUTE)
        return None if active_route_key is None else str(active_route_key)

    @property
    def _active_route(self):
        """Return the active route for the current meter context."""
        if self._selected_meter is not None:
            return get_active_route_for_meter(
                self._selected_meter,
                bus_entry_data=self._config_entry.data,
            )
        return get_active_route(self._config_entry.data)

    @property
    def _selected_meter(self) -> ConfiguredMeter | None:
        """Return the currently selected shared-bus meter for route management."""
        if self._selected_meter_key is None:
            return None

        for meter in self._configured_meters:
            if self._meter_selection_key(meter) == self._selected_meter_key:
                return meter
        return None

    @property
    def _bus_meter_options(self) -> list[dict[str, str]]:
        """Return selectable bus-meter options for route management."""
        options: list[dict[str, str]] = []
        for meter in self._configured_meters:
            profile = get_profile(meter.family, meter.variant)
            active_route = get_active_route_for_meter(
                meter,
                bus_entry_data=self._config_entry.data,
            )
            options.append(
                {
                    "value": self._meter_selection_key(meter),
                    "label": (
                        f"{meter.name} | {profile.title} | "
                        f"{active_route.transport.value} | slave {active_route.slave_id}"
                    ),
                }
            )
        return options

    @property
    def _meter_route_action_options(self) -> list[dict[str, str]]:
        """Return route-management actions for one selected bus meter."""
        return [
            {
                "value": OPTION_ACTION_UPDATE_CONNECTION,
                "label": "Update active route",
            },
            {
                "value": OPTION_ACTION_ADD_ROUTE,
                "label": "Add another route",
            },
            {
                "value": OPTION_ACTION_SWITCH_ROUTE,
                "label": "Switch active route",
            },
        ]

    @property
    def _update_connection_defaults(self) -> dict[str, Any]:
        """Return form defaults for editing the current active route."""
        return {
            **self._connection_data_from_route(self._active_route),
            CONF_SLAVE_ID: self._active_route.slave_id,
            CONF_SCAN_INTERVAL: int(self._config_entry.data[CONF_SCAN_INTERVAL]),
        }

    def _transport_supports_helper_only_routes(
        self,
        transport: TransportType,
    ) -> bool:
        """Return whether one transport supports helper/provisioning-only routes."""
        return transport in {
            TransportType.BLUETOOTH,
            TransportType.BLUETOOTH_PROXY,
        }

    async def _async_add_route_from_user_input(
        self,
        transport: TransportType,
        user_input: dict[str, Any],
        errors: dict[str, str],
    ) -> FlowResult | None:
        """Validate and persist one additional route from submitted form data."""
        connection_data = normalize_connection_data(transport, user_input)
        candidate_data = self._candidate_entry_data_for_route(
            transport=transport,
            connection_data=connection_data,
            slave_id=int(user_input[CONF_SLAVE_ID]),
            scan_interval=int(self._config_entry.data[CONF_SCAN_INTERVAL]),
        )
        route_validation_data = self._route_validation_entry_data(candidate_data)
        gatt_validation_data = bluetooth_gatt_validation_data(route_validation_data)
        validation_data = bluetooth_modbus_pairing_validation_data(
            route_validation_data
        )
        gatt_validated = False
        modbus_validated = False
        try:
            await self._async_validate_bluetooth_gatt_identity(gatt_validation_data)
            gatt_validated = True
            if transport is not TransportType.BLUETOOTH:
                await self._async_validate_modbus_config(validation_data)
            modbus_validated = True
            await self._async_validate_entry_identity(validation_data)
        except IneproBluetoothDeviceNotFound:
            errors["base"] = "bluetooth_device_not_found"
        except IneproConnectionError as err:
            reason = (
                bluetooth_validation_error_reason(err, transport)
                if transport is TransportType.BLUETOOTH
                and (not gatt_validated or modbus_validated)
                else connection_error_reason(err, transport)
            )
            errors["base"] = (
                "bluetooth_not_paired"
                if (
                    transport is TransportType.BLUETOOTH
                    and reason
                    in {
                        "bluetooth_not_paired",
                        "bluetooth_pairing_failed",
                    }
                )
                else reason
            )
        except IneproIdentityError:
            errors["base"] = "invalid_identity"
        else:
            new_route = build_route_from_entry_data(
                candidate_data,
                purpose=str(self._route_selection[CONF_ROUTE_PURPOSE]),
            )
            preserved_routes = tuple(
                route
                for route in self._configured_routes
                if build_route_key(route) != build_route_key(new_route)
            )
            routes = (*preserved_routes, new_route)
            active_route_key = self._active_route_key
            if str(self._route_selection[CONF_ROUTE_PURPOSE]) == ROUTE_PURPOSE_ACTIVE:
                active_route_key = build_route_key(new_route)

            new_data = self._apply_routes_to_entry(
                updated_data=candidate_data,
                routes=routes,
                active_route_key=active_route_key,
            )
            return await self._async_finish_entry_update(
                data=new_data,
            )

        return None

    def _async_discover_route_bluetooth_meters(self):
        """Return HA Bluetooth discoveries that can belong to the current meter."""
        discovered_meters = self._async_discover_grow_bluetooth_meters()
        route_serial = self._route_meter_serial_number
        if route_serial is None:
            return discovered_meters
        return tuple(
            discovered_meter
            for discovered_meter in discovered_meters
            if discovered_meter.serial_number == route_serial
        )

    def _get_discovered_bluetooth_meter(
        self,
        selected_key: str,
    ):
        """Return the previously discovered Bluetooth meter matching the key."""
        for discovered_meter in self._discovered_bluetooth_devices:
            if bluetooth_meter_key(discovered_meter) == selected_key:
                return discovered_meter
        raise ValueError(
            f"Unknown discovered Bluetooth meter selection: {selected_key}"
        )

    @property
    def _route_meter_serial_number(self) -> str | None:
        """Return the serial number for the meter whose route is being edited."""
        if self._selected_meter is not None:
            return configured_entry_serial_number(
                {
                    CONF_NAME: self._selected_meter.name,
                    CONF_SERIAL_NUMBER: self._selected_meter.serial_number,
                }
            )
        return configured_entry_serial_number(self._config_entry.data)

    @property
    def _route_meter_display_name(self) -> str:
        """Return a user-facing name for the meter whose route is being edited."""
        if self._selected_meter is not None:
            return self._selected_meter.name
        return str(self._config_entry.data.get(CONF_NAME, self._config_entry.title))

    def _connection_data_from_route(self, route: ConfiguredRoute) -> dict[str, Any]:
        """Return normalized top-level connection fields for one configured route."""
        data: dict[str, Any] = {
            CONF_TRANSPORT: route.transport.value,
            CONF_TIMEOUT: route.timeout,
        }
        if route.transport is TransportType.SERIAL:
            data.update(
                {
                    CONF_SERIAL_PORT: str(route.serial_port),
                    CONF_BAUDRATE: int(route.baudrate),
                    CONF_BYTESIZE: int(route.bytesize),
                    CONF_PARITY: str(route.parity),
                    CONF_STOPBITS: int(route.stopbits),
                }
            )
        elif route.transport is TransportType.BLUETOOTH:
            data[CONF_BLUETOOTH_ADDRESS] = str(route.bluetooth_address)
            if route.bluetooth_name:
                data[CONF_BLUETOOTH_NAME] = route.bluetooth_name
        elif route.transport is TransportType.BLUETOOTH_PROXY:
            data.update(
                {
                    CONF_HOST: str(route.host),
                    CONF_PORT: int(route.port),
                    CONF_BLUETOOTH_ADDRESS: str(route.bluetooth_address),
                }
            )
            if route.bluetooth_name:
                data[CONF_BLUETOOTH_NAME] = route.bluetooth_name
        else:
            data.update(
                {
                    CONF_HOST: str(route.host),
                    CONF_PORT: int(route.port),
                }
            )
        return data

    def _meter_selection_key(self, meter: ConfiguredMeter) -> str:
        """Build the selector key for one shared-bus meter."""
        return build_meter_key(meter)

    def _candidate_entry_data_for_route(
        self,
        *,
        transport: TransportType,
        connection_data: dict[str, Any],
        slave_id: int,
        scan_interval: int,
    ) -> dict[str, Any]:
        """Build validation-ready entry data for the current route-edit context."""
        base_data = {
            CONF_TRANSPORT: transport.value,
            **connection_data,
            CONF_SLAVE_ID: int(slave_id),
            CONF_SCAN_INTERVAL: int(scan_interval),
        }
        if self._selected_meter is not None:
            meter = self._selected_meter
            base_data.update(
                {
                    CONF_FAMILY: meter.family,
                    CONF_VARIANT: meter.variant,
                    CONF_NAME: meter.name,
                }
            )
            if meter.serial_number is not None:
                base_data[CONF_SERIAL_NUMBER] = meter.serial_number
            return base_data

        return {
            **self._config_entry.data,
            **base_data,
        }

    def _route_validation_entry_data(
        self, entry_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Return top-level route data without stored route-selection metadata."""
        return {
            key: value
            for key, value in entry_data.items()
            if key not in {CONF_ROUTES, CONF_ACTIVE_ROUTE}
        }

    def _apply_routes_to_entry(
        self,
        *,
        updated_data: dict[str, Any],
        routes: tuple[ConfiguredRoute, ...],
        active_route_key: str | None,
    ) -> dict[str, Any]:
        """Apply route changes to either a single-meter or shared-bus entry."""
        if self._selected_meter is None:
            return with_routes_applied(
                updated_data,
                routes=routes,
                active_route_key=active_route_key,
            )

        selected_meter = self._selected_meter
        assert selected_meter is not None
        updated_meter = with_meter_routes(
            selected_meter,
            routes,
            active_route_key=active_route_key,
        )
        return {
            **self._config_entry.data,
            CONF_SCAN_INTERVAL: int(updated_data[CONF_SCAN_INTERVAL]),
            CONF_METERS: [
                serialize_configured_meter(
                    ensure_bus_meter_routes(
                        updated_meter
                        if self._meter_selection_key(meter)
                        == self._meter_selection_key(selected_meter)
                        else meter,
                        bus_entry_data=self._config_entry.data,
                    )
                )
                for meter in self._configured_meters
            ],
        }
