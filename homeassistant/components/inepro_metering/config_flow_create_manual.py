"""Manual creation workflow steps for the Inepro Metering config flow."""

from typing import Any

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.data_entry_flow import FlowResult

from .bluetooth import IneproBluetoothDeviceNotFound
from .config_flow_schemas import (
    UNSELECTED_TRANSPORT,
    build_connection_schema,
    build_device_kind_schema,
    build_family_schema,
    build_model_schema,
    build_setup_method_schema,
    build_transport_schema,
)
from .config_flow_shared import (
    IneproIdentityError,
    bluetooth_gatt_validation_data,
    bluetooth_modbus_pairing_validation_data,
    bluetooth_setup_identity_error_reason,
    bluetooth_validation_error_reason,
    build_unique_id,
    connection_error_reason,
    normalize_connection_data,
    user_visible_transports,
)
from .const import (
    CONF_DEVICE_KIND,
    CONF_FAMILY,
    CONF_SERIAL_NUMBER,
    CONF_SETUP_METHOD,
    CONF_SLAVE_ID,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DEVICE_KIND_GATEWAY,
    SETUP_METHOD_SCAN_BLUETOOTH,
    SETUP_METHOD_SCAN_SERIAL,
    SETUP_METHOD_SCAN_TCP_GATEWAY,
    MeterFamily,
    TransportType,
)
from .discovery import parse_grow_serial_number
from .entry_data import (
    ConfiguredMeter,
    build_route_from_entry_data,
    build_route_key,
    get_configured_routes,
    is_bus_entry,
    with_routes_applied,
)
from .modbus import IneproConnectionError
from .models import (
    MeterProfile,
    get_profile,
    get_profiles_for_family,
    get_supported_families,
)


class CreateManualFlowMixin:
    """Manual creation steps for new Inepro Metering entries."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial meter-vs-gateway selection step."""
        if user_input is not None:
            if CONF_FAMILY in user_input:
                self._meter_selection = {
                    CONF_FAMILY: MeterFamily(user_input[CONF_FAMILY]).value,
                }
                if self._selected_family is MeterFamily.GROW:
                    return await self.async_step_setup_method()
                return await self.async_step_model()

            self._meter_selection = {}
            if user_input[CONF_DEVICE_KIND] == DEVICE_KIND_GATEWAY:
                return await self.async_step_gateway_setup_method()
            return await self.async_step_family()

        return self.async_show_form(
            step_id="user",
            data_schema=build_device_kind_schema(),
        )

    async def async_step_family(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the family selection step for energy meters."""
        if user_input is not None:
            self._meter_selection = {
                CONF_FAMILY: MeterFamily(user_input[CONF_FAMILY]).value,
            }
            if self._selected_family is MeterFamily.GROW:
                return await self.async_step_setup_method()
            return await self.async_step_model()

        supported_families = get_supported_families()
        default_family = supported_families[0]

        return self.async_show_form(
            step_id="family",
            data_schema=build_family_schema(supported_families, default_family),
        )

    async def async_step_setup_method(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose whether to add a meter manually or scan a shared bus."""
        if user_input is not None:
            if user_input[CONF_SETUP_METHOD] == SETUP_METHOD_SCAN_SERIAL:
                return await self.async_step_serial_scan()
            if user_input[CONF_SETUP_METHOD] == SETUP_METHOD_SCAN_TCP_GATEWAY:
                return await self.async_step_gateway_scan()
            if user_input[CONF_SETUP_METHOD] == SETUP_METHOD_SCAN_BLUETOOTH:
                return await self.async_step_bluetooth_scan()
            return await self.async_step_model()

        return self.async_show_form(
            step_id="setup_method",
            data_schema=build_setup_method_schema(),
        )

    async def async_step_model(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the model selection step for the chosen family."""
        family = self._selected_family
        profiles = get_profiles_for_family(family)
        default_variant = next(iter(profiles))

        if user_input is not None:
            profile = get_profile(family, user_input[CONF_VARIANT])
            configured_name = (
                str(user_input.get(CONF_NAME, "")).strip() or profile.title
            )
            parsed_serial = parse_grow_serial_number(configured_name)

            self._meter_selection.update(
                {
                    CONF_NAME: configured_name,
                    CONF_VARIANT: profile.variant,
                    CONF_SLAVE_ID: int(user_input[CONF_SLAVE_ID]),
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                }
            )
            if parsed_serial is not None:
                self._meter_selection[CONF_SERIAL_NUMBER] = parsed_serial.serial_number
            else:
                self._meter_selection.pop(CONF_SERIAL_NUMBER, None)
            return await self.async_step_transport()

        return self.async_show_form(
            step_id="model",
            data_schema=build_model_schema(profiles, default_variant),
        )

    async def async_step_transport(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Select the transport for the chosen meter model."""
        supported_transports = self._available_transports_for_current_flow
        errors: dict[str, str] = {}

        if len(supported_transports) == 1:
            self._meter_selection[CONF_TRANSPORT] = supported_transports[0].value
            return await self.async_step_connection()

        if user_input is not None:
            if (
                user_input[CONF_TRANSPORT] == UNSELECTED_TRANSPORT
                or TransportType(user_input[CONF_TRANSPORT]) not in supported_transports
            ):
                errors["base"] = "transport_required"
            else:
                self._meter_selection[CONF_TRANSPORT] = user_input[CONF_TRANSPORT]
                return await self.async_step_connection()

        selected_transport = self._meter_selection.get(CONF_TRANSPORT)
        if selected_transport == UNSELECTED_TRANSPORT:
            selected_transport = None
        if errors:
            self._meter_selection.pop(CONF_TRANSPORT, None)
            selected_transport = None
        return self.async_show_form(
            step_id="transport",
            data_schema=build_transport_schema(
                supported_transports,
                selected_transport=selected_transport,
            ),
            errors=errors,
        )

    async def async_step_connection(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Collect transport specific connection settings."""
        errors: dict[str, str] = {}
        transport = TransportType(self._meter_selection[CONF_TRANSPORT])
        connection_defaults = self._connection_form_defaults(
            transport=transport,
            user_input=user_input,
        )

        if user_input is not None:
            connection_data = normalize_connection_data(transport, user_input)
            entry_data = {**self._meter_selection, **connection_data}
            gatt_validation_data = bluetooth_gatt_validation_data(entry_data)
            gatt_validated = False

            try:
                gatt_serial = await self._async_validate_bluetooth_gatt_identity(
                    gatt_validation_data
                )
                if gatt_serial is not None and CONF_SERIAL_NUMBER not in entry_data:
                    entry_data[CONF_SERIAL_NUMBER] = gatt_serial
                    gatt_validation_data[CONF_SERIAL_NUMBER] = gatt_serial
                gatt_validated = True
                validation_data = bluetooth_modbus_pairing_validation_data(entry_data)
                if transport is not TransportType.BLUETOOTH:
                    await self._async_validate_modbus_config(validation_data)
            except IneproBluetoothDeviceNotFound:
                errors["base"] = "bluetooth_device_not_found"
            except IneproIdentityError:
                errors["base"] = "invalid_identity"
            except IneproConnectionError as err:
                errors["base"] = (
                    bluetooth_validation_error_reason(err, transport)
                    if transport is TransportType.BLUETOOTH and not gatt_validated
                    else connection_error_reason(err, transport)
                )
            else:
                if self._is_reconfigure_flow:
                    try:
                        await self._async_validate_entry_identity(validation_data)
                    except IneproBluetoothDeviceNotFound:
                        errors["base"] = "bluetooth_device_not_found"
                    except IneproConnectionError as err:
                        errors["base"] = bluetooth_setup_identity_error_reason(
                            err,
                            transport,
                        )
                    except IneproIdentityError:
                        errors["base"] = "invalid_identity"
                    else:
                        return self._async_finish_reconfigure_connection(
                            transport=transport,
                            entry_data=entry_data,
                        )
                    return self.async_show_form(
                        step_id="connection",
                        data_schema=build_connection_schema(
                            transport,
                            connection_defaults,
                        ),
                        errors=errors,
                    )

                try:
                    serial_number = (
                        await self._async_resolve_entry_serial_number_for_creation(
                            validation_data
                        )
                    )
                except IneproBluetoothDeviceNotFound:
                    errors["base"] = "bluetooth_device_not_found"
                except IneproConnectionError as err:
                    errors["base"] = bluetooth_setup_identity_error_reason(
                        err,
                        transport,
                    )
                else:
                    expected_serial = entry_data.get(CONF_SERIAL_NUMBER)
                    if (
                        transport is TransportType.BLUETOOTH
                        and expected_serial is not None
                        and serial_number is not None
                        and str(serial_number) != str(expected_serial)
                    ):
                        errors["base"] = "invalid_identity"
                        return self.async_show_form(
                            step_id="connection",
                            data_schema=build_connection_schema(
                                transport,
                                connection_defaults,
                            ),
                            errors=errors,
                        )
                    if serial_number is not None:
                        entry_data[CONF_SERIAL_NUMBER] = serial_number
                        self._meter_selection[CONF_SERIAL_NUMBER] = serial_number
                    elif self._selected_family is MeterFamily.GROW:
                        errors["base"] = "cannot_connect"
                        return self.async_show_form(
                            step_id="connection",
                            data_schema=build_connection_schema(
                                transport,
                                connection_defaults,
                            ),
                            errors=errors,
                        )

                    if (
                        transport is TransportType.BLUETOOTH
                        and serial_number is not None
                    ):
                        existing_entry = self._find_entry_containing_meter_serial(
                            str(serial_number)
                        )
                        if existing_entry is not None:
                            errors["base"] = (
                                "already_configured_via_gateway"
                                if is_bus_entry(existing_entry.data)
                                else "already_configured"
                            )
                            return self.async_show_form(
                                step_id="connection",
                                data_schema=build_connection_schema(
                                    transport,
                                    connection_defaults,
                                ),
                                errors=errors,
                            )

                    if transport in {TransportType.SERIAL, TransportType.TCP_GATEWAY}:
                        parsed_serial = (
                            None
                            if serial_number is None
                            else parse_grow_serial_number(serial_number)
                        )
                        meter = ConfiguredMeter(
                            family=self._meter_selection[CONF_FAMILY],
                            name=self._meter_selection[CONF_NAME],
                            variant=self._meter_selection[CONF_VARIANT],
                            slave_id=int(self._meter_selection[CONF_SLAVE_ID]),
                            serial_number=serial_number,
                            product_code=(
                                None
                                if parsed_serial is None
                                else parsed_serial.product_code
                            ),
                        )
                        if transport is TransportType.TCP_GATEWAY:
                            return await self._async_upsert_tcp_gateway_bus(
                                connection_data,
                                meters=(meter,),
                                scan_interval=int(
                                    self._meter_selection[CONF_SCAN_INTERVAL]
                                ),
                            )

                        return await self._async_upsert_serial_bus(
                            connection_data,
                            meters=(meter,),
                            scan_interval=int(
                                self._meter_selection[CONF_SCAN_INTERVAL]
                            ),
                        )

                    entry_data = with_routes_applied(
                        entry_data,
                        routes=(build_route_from_entry_data(entry_data),),
                    )
                    await self.async_set_unique_id(build_unique_id(entry_data))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=self._meter_selection[CONF_NAME],
                        data=entry_data,
                    )

        return self.async_show_form(
            step_id="connection",
            data_schema=build_connection_schema(transport, connection_defaults),
            errors=errors,
        )

    def _async_finish_reconfigure_connection(
        self,
        *,
        transport: TransportType,
        entry_data: dict[str, Any],
    ) -> FlowResult:
        """Persist a reconfigured single-meter entry without changing identity."""
        existing_routes = get_configured_routes(self._config_entry.data)
        updated_route = build_route_from_entry_data(entry_data)
        preserved_routes = tuple(
            route for route in existing_routes if route.transport is not transport
        )
        new_data = with_routes_applied(
            {
                **self._config_entry.data,
                **entry_data,
            },
            routes=(*preserved_routes, updated_route),
            active_route_key=build_route_key(updated_route),
        )
        return self.async_update_reload_and_abort(
            self._config_entry,
            unique_id=self._config_entry.unique_id,
            title=self._config_entry.title,
            data=new_data,
        )

    def _connection_form_defaults(
        self,
        *,
        transport: TransportType,
        user_input: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Return user input or reconfigure defaults for the connection form."""
        if user_input is not None:
            return user_input
        if not self._is_reconfigure_flow:
            return None
        return self._reconfigure_connection_defaults(transport)

    def _reconfigure_connection_defaults(
        self,
        transport: TransportType,
    ) -> dict[str, Any] | None:
        """Return saved connection details for one transport during reconfigure."""
        for route in get_configured_routes(self._config_entry.data):
            if route.transport is not transport:
                continue

            defaults: dict[str, Any] = {
                CONF_TRANSPORT: route.transport.value,
                "timeout": route.timeout,
            }
            if route.transport is TransportType.SERIAL:
                defaults.update(
                    {
                        "serial_port": str(route.serial_port),
                        "baudrate": int(route.baudrate),
                        "bytesize": int(route.bytesize),
                        "parity": str(route.parity),
                        "stopbits": int(route.stopbits),
                    }
                )
            elif route.transport is TransportType.BLUETOOTH:
                defaults["bluetooth_address"] = str(route.bluetooth_address)
                if route.bluetooth_name:
                    defaults["bluetooth_name"] = route.bluetooth_name
            elif route.transport is TransportType.BLUETOOTH_PROXY:
                defaults.update(
                    {
                        "host": str(route.host),
                        "port": int(route.port),
                        "bluetooth_address": str(route.bluetooth_address),
                    }
                )
                if route.bluetooth_name:
                    defaults["bluetooth_name"] = route.bluetooth_name
            else:
                defaults.update(
                    {
                        "host": str(route.host),
                        "port": int(route.port),
                    }
                )
            return defaults

        return None

    @property
    def _available_transports_for_current_flow(self) -> tuple[TransportType, ...]:
        """Return transports that keep the current entry shape stable."""
        current_transport = (
            None
            if not self._is_reconfigure_flow
            else TransportType(self._config_entry.data[CONF_TRANSPORT])
        )
        transports = user_visible_transports(
            self._selected_profile.supported_transports,
            include_transport=current_transport,
        )
        if not self._is_reconfigure_flow:
            return transports

        filtered = tuple(
            transport
            for transport in transports
            if transport not in {TransportType.SERIAL, TransportType.TCP_GATEWAY}
        )
        return filtered or (current_transport,)

    @property
    def _is_reconfigure_flow(self) -> bool:
        """Return whether the current config flow is reconfiguring an entry."""
        return (
            getattr(self, "source", None) == SOURCE_RECONFIGURE
            and getattr(self, "_config_entry", None) is not None
        )

    @property
    def _selected_profile(self) -> MeterProfile:
        """Return the profile picked in the first step."""
        return get_profile(
            self._meter_selection[CONF_FAMILY],
            self._meter_selection[CONF_VARIANT],
        )

    @property
    def _selected_family(self) -> MeterFamily:
        """Return the selected family."""
        return MeterFamily(self._meter_selection[CONF_FAMILY])
