"""Discovery-oriented creation workflow steps for the Inepro Metering config flow."""

import logging
from typing import Any

import voluptuous as vol

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
    UNSELECTED_TRANSPORT,
    build_bluetooth_confirm_schema,
    build_bluetooth_discovered_schema,
    build_discovered_gateway_schema,
    build_discovered_serial_schema,
    build_gateway_discover_schema,
    build_gateway_scan_schema,
    build_gateway_setup_method_schema,
    build_serial_scan_schema,
    build_transport_schema,
)
from .config_flow_shared import (
    CONF_DISCOVERED_BLUETOOTH_METER,
    CONF_DISCOVERED_METERS,
    IneproIdentityError,
    bluetooth_gatt_validation_data,
    bluetooth_meter_key,
    bluetooth_modbus_pairing_validation_data,
    bluetooth_setup_identity_error_reason,
    bluetooth_validation_error_reason,
    normalize_connection_data,
)
from .const import (
    CONF_BLUETOOTH_ADDRESS,
    CONF_BLUETOOTH_NAME,
    CONF_DISCOVERED_GATEWAY,
    CONF_FAMILY,
    CONF_GATEWAY_DISCOVERY_TARGET,
    CONF_GATEWAY_SETUP_METHOD,
    CONF_SERIAL_NUMBER,
    CONF_SLAVE_ID,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DEFAULT_GATEWAY_SCAN_SLAVE_ID_END,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_TIMEOUT,
    DOMAIN,
    GATEWAY_SETUP_METHOD_SCAN_NETWORK,
    MeterFamily,
    TransportType,
)
from .discovery import (
    CONF_SLAVE_ID_END,
    CONF_SLAVE_ID_START,
    infer_grow_variant,
    parse_grow_serial_number,
)
from .entry_data import (
    ConfiguredMeter,
    build_route_from_entry_data,
    get_configured_meters,
    is_bus_entry,
    update_single_meter_bluetooth_route_from_discovery,
    update_single_meter_tcp_route_from_zeroconf,
    with_routes_applied,
)
from .modbus import IneproConnectionError

_LOGGER = logging.getLogger(__name__)

GROW_MDNS_SERVICE_TYPE = "_modbus._tcp.local."
KNOWN_GROW_MDNS_MODELS = {"879-3120"}
KNOWN_GROW_MDNS_NAME_PREFIXES = ("inepro_", "wago_")
KNOWN_GROW_MDNS_VENDOR_HINTS = ("inepro", "wago")
GROW_MDNS_DIRECT_TCP_TRANSPORTS = (
    TransportType.TCP_WIFI,
    TransportType.TCP_ETHERNET,
)


def _decode_zeroconf_text(value: Any) -> str:
    """Decode one Zeroconf TXT key or value for matching."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8").strip()
        except UnicodeDecodeError:
            return value.hex()
    return str(value).strip()


def _decode_zeroconf_properties(properties: dict[str, Any]) -> dict[str, str]:
    """Decode Zeroconf TXT properties with case-insensitive keys."""
    decoded: dict[str, str] = {}
    for key, value in properties.items():
        decoded_key = _decode_zeroconf_text(key).lower()
        if not decoded_key:
            continue
        decoded[decoded_key] = _decode_zeroconf_text(value)
    return decoded


def _has_grow_mdns_ownership_hint(
    discovery_info: Any,
    *,
    vendor: str,
    model: str,
) -> bool:
    """Return whether an mDNS Modbus service looks like an inepro GROW meter."""
    normalized_vendor = vendor.casefold()
    if any(hint in normalized_vendor for hint in KNOWN_GROW_MDNS_VENDOR_HINTS):
        return True

    if model in KNOWN_GROW_MDNS_MODELS:
        return True

    service_text = f"{discovery_info.hostname}\n{discovery_info.name}".casefold()
    return any(prefix in service_text for prefix in KNOWN_GROW_MDNS_NAME_PREFIXES)


def _exception_chain_summary(err: BaseException) -> str:
    """Return a compact exception chain summary for bench diagnostics."""
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = err
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).strip()
        parts.append(
            type(current).__name__
            if not message
            else f"{type(current).__name__}: {message}"
        )
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)


class CreateDiscoveryFlowMixin:
    """Discovery-driven creation steps for new Inepro Metering entries."""

    async def async_step_zeroconf(
        self,
        discovery_info: Any,
    ) -> FlowResult:
        """Handle a GROW Modbus TCP discovery from Home Assistant Zeroconf."""
        _LOGGER.debug(
            "Zeroconf candidate received: type=%s name=%s hostname=%s address=%s port=%s",
            discovery_info.type,
            discovery_info.name,
            discovery_info.hostname,
            discovery_info.ip_address,
            discovery_info.port,
        )

        if discovery_info.type != GROW_MDNS_SERVICE_TYPE:
            _LOGGER.debug(
                "Zeroconf candidate rejected: unsupported service type %s",
                discovery_info.type,
            )
            return self.async_abort(reason="not_supported")

        properties = _decode_zeroconf_properties(discovery_info.properties)
        serial_number = properties.get("serial", "").strip()
        vendor = properties.get("vendor", "").strip()
        model = properties.get("model", "").strip()

        _LOGGER.debug(
            "Zeroconf candidate TXT extracted: serial=%s model=%s vendor=%s",
            serial_number or "<missing>",
            model or "<missing>",
            vendor or "<missing>",
        )

        if not serial_number:
            _LOGGER.debug("Zeroconf candidate rejected: missing TXT serial")
            return self.async_abort(reason="not_supported")

        parsed_serial = parse_grow_serial_number(serial_number)
        if parsed_serial is None:
            _LOGGER.debug(
                "Zeroconf candidate rejected: unsupported GROW serial format %s",
                serial_number,
            )
            return self.async_abort(reason="not_supported")

        if not _has_grow_mdns_ownership_hint(
            discovery_info, vendor=vendor, model=model
        ):
            _LOGGER.debug(
                "Zeroconf candidate rejected: no inepro/GROW ownership hint for serial=%s",
                serial_number,
            )
            return self.async_abort(reason="not_supported")

        if discovery_info.port is None:
            _LOGGER.debug(
                "Zeroconf candidate rejected: missing service port for serial=%s",
                serial_number,
            )
            return self.async_abort(reason="not_supported")

        host = str(discovery_info.ip_address)
        port = int(discovery_info.port)
        variant = infer_grow_variant(serial_number)
        if variant is None:
            _LOGGER.debug(
                "Zeroconf candidate rejected: no supported GROW variant for serial=%s",
                serial_number,
            )
            return self.async_abort(reason="not_supported")

        _LOGGER.debug(
            "Zeroconf candidate accepted: serial=%s host=%s port=%s model=%s vendor=%s",
            serial_number,
            host,
            port,
            model or "<missing>",
            vendor or "<missing>",
        )

        existing_entry = self._find_entry_containing_meter_serial(serial_number)
        if existing_entry is not None:
            if is_bus_entry(existing_entry.data):
                _LOGGER.debug(
                    "Zeroconf rediscovery ignored for serial=%s: already configured via shared bus entry %s",
                    serial_number,
                    existing_entry.entry_id,
                )
                return self.async_abort(reason="already_configured_via_gateway")

            updated_data = update_single_meter_tcp_route_from_zeroconf(
                existing_entry.data,
                host=host,
                port=port,
            )
            if existing_entry.unique_id != serial_number:
                _LOGGER.debug(
                    "Zeroconf rediscovery updating legacy entry %s: %s:%s",
                    existing_entry.entry_id,
                    host,
                    port,
                )
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data=updated_data,
                )
                return self.async_abort(reason="already_configured")

            _LOGGER.debug(
                "Zeroconf rediscovery detected for serial=%s; refreshing direct TCP endpoint to %s:%s",
                serial_number,
                host,
                port,
            )
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured(updates=updated_data)
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        self._zeroconf_discovery = {
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: serial_number,
            CONF_SERIAL_NUMBER: serial_number,
            CONF_VARIANT: variant,
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SLAVE_ID: DEFAULT_SLAVE_ID,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        }
        self.context["title_placeholders"] = {
            CONF_NAME: serial_number,
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Confirm a Zeroconf-discovered GROW meter."""
        errors: dict[str, str] = {}
        entry_data = dict(self._zeroconf_discovery)
        selected_transport: str | None = None

        if user_input is not None:
            selected_transport = str(
                user_input.get(CONF_TRANSPORT, UNSELECTED_TRANSPORT)
            )
            try:
                transport = TransportType(selected_transport)
            except ValueError:
                errors["base"] = "transport_required"
                selected_transport = None
            else:
                if (
                    selected_transport == UNSELECTED_TRANSPORT
                    or transport not in GROW_MDNS_DIRECT_TCP_TRANSPORTS
                ):
                    errors["base"] = "transport_required"
                    selected_transport = None
                else:
                    entry_data[CONF_TRANSPORT] = transport.value

            if not errors:
                try:
                    await self._async_validate_modbus_config(entry_data)
                except IneproConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    try:
                        await self._async_validate_entry_identity(entry_data)
                    except IneproIdentityError:
                        _LOGGER.debug(
                            "Zeroconf identity validation failed: TXT serial %s does not match live meter",
                            entry_data[CONF_SERIAL_NUMBER],
                        )
                        errors["base"] = "invalid_identity"
                    except IneproConnectionError:
                        _LOGGER.debug(
                            "Zeroconf identity validation failed: unable to read live serial for %s",
                            entry_data[CONF_SERIAL_NUMBER],
                        )
                        errors["base"] = "cannot_validate"
                    else:
                        _LOGGER.debug(
                            "Zeroconf identity validation succeeded for serial=%s host=%s port=%s transport=%s",
                            entry_data[CONF_SERIAL_NUMBER],
                            entry_data[CONF_HOST],
                            entry_data[CONF_PORT],
                            entry_data[CONF_TRANSPORT],
                        )
                        entry_data = with_routes_applied(
                            entry_data,
                            routes=(build_route_from_entry_data(entry_data),),
                        )
                        await self.async_set_unique_id(
                            str(entry_data[CONF_SERIAL_NUMBER])
                        )
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title=str(entry_data[CONF_SERIAL_NUMBER]),
                            data=entry_data,
                        )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=build_transport_schema(
                GROW_MDNS_DIRECT_TCP_TRANSPORTS,
                selected_transport=selected_transport,
            ),
            description_placeholders={
                CONF_NAME: str(entry_data[CONF_SERIAL_NUMBER]),
                CONF_HOST: str(entry_data[CONF_HOST]),
                CONF_PORT: str(entry_data[CONF_PORT]),
            },
            errors=errors,
        )

    def _find_entry_containing_meter_serial(self, serial_number: str):
        """Return the configured entry that already owns a physical meter serial."""
        for entry in self.hass.config_entries.async_entries():
            if entry.domain != DOMAIN:
                continue
            for meter in get_configured_meters(entry.data, title=entry.title):
                if meter.serial_number == serial_number:
                    return entry
        return None

    async def async_step_gateway_setup_method(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose whether to discover a gateway or enter its IP manually."""
        if user_input is not None:
            if (
                user_input[CONF_GATEWAY_SETUP_METHOD]
                == GATEWAY_SETUP_METHOD_SCAN_NETWORK
            ):
                return await self.async_step_gateway_discover()

            self._selected_discovered_gateway = None
            self._gateway_scan_form_defaults = {}
            return await self.async_step_gateway_scan()

        return self.async_show_form(
            step_id="gateway_setup_method",
            data_schema=build_gateway_setup_method_schema(),
        )

    async def async_step_bluetooth(
        self,
        discovery_info,
    ) -> FlowResult:
        """Handle a GROW Bluetooth discovery from Home Assistant."""
        discovered_meter = self._grow_bluetooth_meter_from_service_info(discovery_info)
        if discovered_meter is None:
            return self.async_abort(reason="not_supported")

        _LOGGER.debug(
            "Bluetooth discovery received for serial=%s address=%s name=%s",
            discovered_meter.serial_number,
            discovered_meter.address,
            discovered_meter.bluetooth_name,
        )

        existing_entry = self._find_entry_containing_meter_serial(
            discovered_meter.serial_number
        )
        if existing_entry is not None:
            if is_bus_entry(existing_entry.data):
                _LOGGER.debug(
                    "Bluetooth rediscovery ignored for serial=%s: already configured via shared bus entry %s",
                    discovered_meter.serial_number,
                    existing_entry.entry_id,
                )
                return self.async_abort(reason="already_configured_via_gateway")

            if (
                TransportType(existing_entry.data[CONF_TRANSPORT])
                is TransportType.BLUETOOTH
            ):
                updated_data = update_single_meter_bluetooth_route_from_discovery(
                    existing_entry.data,
                    address=discovered_meter.address,
                    bluetooth_name=discovered_meter.bluetooth_name,
                )
                _LOGGER.debug(
                    "Bluetooth rediscovery updating direct entry %s for serial=%s address=%s name=%s",
                    existing_entry.entry_id,
                    discovered_meter.serial_number,
                    discovered_meter.address,
                    discovered_meter.bluetooth_name,
                )
                if existing_entry.unique_id != discovered_meter.serial_number:
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data=updated_data,
                    )
                    return self.async_abort(reason="already_configured")

                await self.async_set_unique_id(discovered_meter.serial_number)
                self._abort_if_unique_id_configured(updates=updated_data)
                return self.async_abort(reason="already_configured")

            _LOGGER.debug(
                "Bluetooth rediscovery ignored for serial=%s: already configured through %s entry %s",
                discovered_meter.serial_number,
                existing_entry.data[CONF_TRANSPORT],
                existing_entry.entry_id,
            )
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(discovered_meter.serial_number)
        self._abort_if_unique_id_configured()

        self._discovered_bluetooth_devices = (discovered_meter,)
        self.context["title_placeholders"] = {
            CONF_NAME: discovered_meter.serial_number,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_scan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Scan Home Assistant's Bluetooth cache for GROW meters."""
        self._discovered_bluetooth_devices = (
            self._async_discover_grow_bluetooth_meters()
        )
        if self._discovered_bluetooth_devices:
            return await self.async_step_bluetooth_discovered()

        return self.async_show_form(
            step_id="bluetooth_scan",
            data_schema=vol.Schema({}),
            errors={"base": "no_bluetooth_devices_found"},
        )

    async def async_step_bluetooth_discovered(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose a discovered GROW Bluetooth meter."""
        errors: dict[str, str] = {}

        if user_input is not None:
            discovered_meter = self._get_discovered_bluetooth_meter(
                user_input[CONF_DISCOVERED_BLUETOOTH_METER]
            )
            return await self._async_create_bluetooth_entry(
                discovered_meter,
                user_input,
                errors,
                step_id="bluetooth_discovered",
            )

        return self.async_show_form(
            step_id="bluetooth_discovered",
            data_schema=build_bluetooth_discovered_schema(
                self._discovered_bluetooth_devices,
                user_input,
            ),
            description_placeholders={
                "count": str(len(self._discovered_bluetooth_devices)),
            },
        )

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Confirm a Bluetooth-discovered GROW meter."""
        errors: dict[str, str] = {}
        discovered_meter = self._discovered_bluetooth_devices[0]

        if user_input is not None:
            return await self._async_create_bluetooth_entry(
                discovered_meter,
                user_input,
                errors,
                step_id="bluetooth_confirm",
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=build_bluetooth_confirm_schema(user_input),
            description_placeholders={
                CONF_NAME: discovered_meter.serial_number,
                "bluetooth_name": discovered_meter.bluetooth_name,
            },
            errors=errors,
        )

    async def async_step_serial_scan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Scan one serial Modbus bus for supported meters."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if int(user_input[CONF_SLAVE_ID_START]) > int(
                user_input[CONF_SLAVE_ID_END]
            ):
                errors["base"] = "invalid_scan_range"
                return self.async_show_form(
                    step_id="serial_scan",
                    data_schema=build_serial_scan_schema(user_input),
                    errors=errors,
                )

            self._bus_scan_connection = normalize_connection_data(
                TransportType.SERIAL,
                user_input,
            )
            self._bus_scan_defaults = {
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                CONF_SLAVE_ID_START: int(user_input[CONF_SLAVE_ID_START]),
                CONF_SLAVE_ID_END: int(user_input[CONF_SLAVE_ID_END]),
            }
            self._bus_scan_transport = TransportType.SERIAL

            try:
                discovered = await self._async_discover_grow_serial_bus(
                    self._bus_scan_connection,
                    slave_id_start=self._bus_scan_defaults[CONF_SLAVE_ID_START],
                    slave_id_end=self._bus_scan_defaults[CONF_SLAVE_ID_END],
                )
            except IneproConnectionError:
                errors["base"] = "cannot_connect"
            else:
                self._discovered_bus_devices = self._filter_new_bus_devices(
                    discovered,
                    connection_data=self._bus_scan_connection,
                    transport=TransportType.SERIAL,
                )
                if not self._discovered_bus_devices:
                    errors["base"] = "no_new_devices_found"
                else:
                    return await self.async_step_discovered()

        return self.async_show_form(
            step_id="serial_scan",
            data_schema=build_serial_scan_schema(user_input),
            errors=errors,
        )

    async def async_step_gateway_scan(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Scan one Modbus TCP gateway for downstream supported meters."""
        errors: dict[str, str] = {}
        gateway_scan_defaults = (
            user_input
            if user_input is not None
            else self._gateway_scan_form_defaults or None
        )

        if user_input is not None:
            if int(user_input[CONF_SLAVE_ID_START]) > int(
                user_input[CONF_SLAVE_ID_END]
            ):
                errors["base"] = "invalid_scan_range"
                return self.async_show_form(
                    step_id="gateway_scan",
                    data_schema=build_gateway_scan_schema(gateway_scan_defaults),
                    errors=errors,
                )

            self._bus_scan_connection = normalize_connection_data(
                TransportType.TCP_GATEWAY,
                user_input,
            )
            selected_gateway = getattr(self, "_selected_discovered_gateway", None)
            if (
                selected_gateway is not None
                and selected_gateway.serial_number
                and self._bus_scan_connection[CONF_HOST] == selected_gateway.host
                and self._bus_scan_connection[CONF_PORT] == selected_gateway.port
            ):
                self._bus_scan_connection[CONF_SERIAL_NUMBER] = (
                    selected_gateway.serial_number
                )
            self._bus_scan_defaults = {
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                CONF_SLAVE_ID_START: int(user_input[CONF_SLAVE_ID_START]),
                CONF_SLAVE_ID_END: int(user_input[CONF_SLAVE_ID_END]),
            }
            self._bus_scan_transport = TransportType.TCP_GATEWAY

            try:
                _LOGGER.debug(
                    "Gateway downstream scan started for %s:%s range=%s-%s",
                    self._bus_scan_connection[CONF_HOST],
                    self._bus_scan_connection[CONF_PORT],
                    self._bus_scan_defaults[CONF_SLAVE_ID_START],
                    self._bus_scan_defaults[CONF_SLAVE_ID_END],
                )
                discovered = await self._async_discover_grow_tcp_gateway(
                    self._bus_scan_connection,
                    slave_id_start=self._bus_scan_defaults[CONF_SLAVE_ID_START],
                    slave_id_end=self._bus_scan_defaults[CONF_SLAVE_ID_END],
                )
            except IneproConnectionError as err:
                _LOGGER.debug(
                    "Gateway downstream scan validation failed for %s:%s: %s",
                    self._bus_scan_connection[CONF_HOST],
                    self._bus_scan_connection[CONF_PORT],
                    err,
                )
                errors["base"] = "cannot_connect"
            else:
                self._discovered_bus_devices = self._filter_new_bus_devices(
                    discovered,
                    connection_data=self._bus_scan_connection,
                    transport=TransportType.TCP_GATEWAY,
                )
                _LOGGER.debug(
                    "Gateway downstream scan completed for %s:%s; meters=%s",
                    self._bus_scan_connection[CONF_HOST],
                    self._bus_scan_connection[CONF_PORT],
                    len(self._discovered_bus_devices),
                )
                if not self._discovered_bus_devices:
                    return await self.async_step_gateway_no_meters()
                return await self.async_step_discovered()

        return self.async_show_form(
            step_id="gateway_scan",
            data_schema=build_gateway_scan_schema(gateway_scan_defaults),
            errors=errors,
        )

    async def async_step_gateway_discover(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Discover TCP gateways on the local network."""
        errors: dict[str, str] = {}
        progress_task = self.async_get_progress_task()
        if progress_task is not None and progress_task.done():
            try:
                self._discovered_gateways = progress_task.result()
            except ValueError:
                self._gateway_discover_errors = {"base": "invalid_scan_target"}
                return self.async_show_progress_done(next_step_id="gateway_discover")

            if self._discovered_gateways:
                return self.async_show_progress_done(next_step_id="gateway_discovered")

            self._gateway_discover_errors = {"base": "no_gateways_found"}
            return self.async_show_progress_done(next_step_id="gateway_discover")

        scan_target = None
        if user_input is not None:
            scan_target_text = str(
                user_input.get(CONF_GATEWAY_DISCOVERY_TARGET, "")
            ).strip()
            scan_target = scan_target_text or None

            progress_task = self.hass.async_create_task(
                self._async_discover_tcp_gateways(scan_target=scan_target)
            )
            return self.async_show_progress(
                step_id="gateway_discover",
                progress_action="gateway_discover",
                progress_task=progress_task,
                description_placeholders={
                    "target": scan_target or "local network",
                },
            )

        errors = getattr(self, "_gateway_discover_errors", {})
        self._gateway_discover_errors = {}

        return self.async_show_form(
            step_id="gateway_discover",
            data_schema=build_gateway_discover_schema(user_input),
            errors=errors,
        )

    async def async_step_gateway_discovered(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose one discovered TCP gateway before scanning its downstream bus."""
        if user_input is not None:
            selected_gateway = self._get_discovered_gateway(
                user_input[CONF_DISCOVERED_GATEWAY]
            )
            self._selected_discovered_gateway = selected_gateway
            self._gateway_scan_form_defaults = {
                CONF_HOST: selected_gateway.host,
                CONF_PORT: selected_gateway.port,
                CONF_TIMEOUT: DEFAULT_TIMEOUT,
                CONF_SLAVE_ID_START: DEFAULT_SLAVE_ID,
                CONF_SLAVE_ID_END: DEFAULT_GATEWAY_SCAN_SLAVE_ID_END,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            }
            return await self.async_step_gateway_scan()

        return self.async_show_form(
            step_id="gateway_discovered",
            data_schema=build_discovered_gateway_schema(
                self._discovered_gateways,
                user_input,
            ),
            description_placeholders={
                "count": str(len(self._discovered_gateways)),
                "gateway": self._gateway_found_summary(self._discovered_gateways[0]),
            },
        )

    async def async_step_gateway_no_meters(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Confirm adding a verified gateway that has no discovered downstream meters."""
        if user_input is not None:
            return await self._async_upsert_tcp_gateway_bus(
                self._bus_scan_connection,
                meters=(),
                scan_interval=self._bus_scan_defaults.get(
                    CONF_SCAN_INTERVAL,
                    DEFAULT_SCAN_INTERVAL,
                ),
            )

        return self.async_show_form(
            step_id="gateway_no_meters",
            data_schema=vol.Schema({}),
            description_placeholders={
                CONF_HOST: str(self._bus_scan_connection[CONF_HOST]),
                CONF_PORT: str(self._bus_scan_connection[CONF_PORT]),
            },
        )

    async def async_step_discovered(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Choose one or more newly discovered meters from the serial scan."""
        if user_input is not None:
            selected_meters = self._get_discovered_meters(
                user_input[CONF_DISCOVERED_METERS]
            )
            if self._bus_scan_transport is TransportType.TCP_GATEWAY:
                return await self._async_upsert_tcp_gateway_bus(
                    self._bus_scan_connection,
                    meters=tuple(
                        ConfiguredMeter(
                            family=discovered_meter.family.value,
                            name=discovered_meter.serial_number,
                            variant=discovered_meter.variant,
                            slave_id=discovered_meter.slave_id,
                            serial_number=discovered_meter.serial_number,
                            product_code=discovered_meter.product_code,
                        )
                        for discovered_meter in selected_meters
                    ),
                    scan_interval=int(user_input[CONF_SCAN_INTERVAL]),
                )

            return await self._async_upsert_serial_bus(
                self._bus_scan_connection,
                meters=tuple(
                    ConfiguredMeter(
                        family=discovered_meter.family.value,
                        name=discovered_meter.serial_number,
                        variant=discovered_meter.variant,
                        slave_id=discovered_meter.slave_id,
                        serial_number=discovered_meter.serial_number,
                        product_code=discovered_meter.product_code,
                    )
                    for discovered_meter in selected_meters
                ),
                scan_interval=int(user_input[CONF_SCAN_INTERVAL]),
            )

        return self.async_show_form(
            step_id="discovered",
            data_schema=build_discovered_serial_schema(
                self._discovered_bus_devices,
                scan_interval_default=self._bus_scan_defaults.get(
                    CONF_SCAN_INTERVAL,
                    DEFAULT_SCAN_INTERVAL,
                ),
            ),
            description_placeholders={
                "count": str(len(self._discovered_bus_devices)),
            },
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

    def _get_discovered_gateway(self, selected_host: str):
        """Return the previously discovered TCP gateway matching the host."""
        for discovered_gateway in self._discovered_gateways:
            if f"{discovered_gateway.host}:{discovered_gateway.port}" == selected_host:
                return discovered_gateway
        raise ValueError(f"Unknown discovered gateway selection: {selected_host}")

    def _gateway_found_summary(self, gateway) -> str:
        """Return a clear verified gateway summary for placeholders."""
        serial = f" serial {gateway.serial_number}" if gateway.serial_number else ""
        return (
            f"Found verified inepro gateway at {gateway.host}:{gateway.port}{serial}."
        )

    async def _async_create_bluetooth_entry(
        self,
        discovered_meter,
        user_input: dict[str, Any],
        errors: dict[str, str],
        *,
        step_id: str,
    ) -> FlowResult:
        """Validate and create a single-meter Bluetooth config entry."""
        existing_entry = self._find_entry_containing_meter_serial(
            discovered_meter.serial_number
        )
        if existing_entry is not None:
            if is_bus_entry(existing_entry.data):
                return self.async_abort(reason="already_configured_via_gateway")

            if (
                TransportType(existing_entry.data[CONF_TRANSPORT])
                is TransportType.BLUETOOTH
            ):
                updated_data = update_single_meter_bluetooth_route_from_discovery(
                    existing_entry.data,
                    address=discovered_meter.address,
                    bluetooth_name=discovered_meter.bluetooth_name,
                )
                if existing_entry.unique_id != discovered_meter.serial_number:
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data=updated_data,
                    )
                    return self.async_abort(reason="already_configured")

                await self.async_set_unique_id(discovered_meter.serial_number)
                self._abort_if_unique_id_configured(updates=updated_data)
                return self.async_abort(reason="already_configured")

            return self.async_abort(reason="already_configured")

        entry_data = {
            CONF_FAMILY: MeterFamily.GROW.value,
            CONF_NAME: discovered_meter.serial_number,
            CONF_SERIAL_NUMBER: discovered_meter.serial_number,
            CONF_VARIANT: discovered_meter.variant,
            CONF_TRANSPORT: discovered_meter.transport.value,
            CONF_BLUETOOTH_ADDRESS: discovered_meter.address,
            CONF_BLUETOOTH_NAME: discovered_meter.bluetooth_name,
            CONF_SLAVE_ID: int(user_input[CONF_SLAVE_ID]),
            CONF_TIMEOUT: int(user_input[CONF_TIMEOUT]),
            CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
        }
        if discovered_meter.transport is TransportType.BLUETOOTH_PROXY:
            entry_data.update(
                {
                    CONF_HOST: discovered_meter.proxy_host,
                    CONF_PORT: discovered_meter.proxy_port,
                }
            )
        gatt_validation_data = bluetooth_gatt_validation_data(entry_data)

        try:
            gatt_serial = await self._async_validate_bluetooth_gatt_identity(
                gatt_validation_data
            )
        except IneproBluetoothDeviceNotFound:
            errors["base"] = "bluetooth_device_not_found"
        except IneproConnectionError as err:
            errors["base"] = bluetooth_validation_error_reason(
                err,
                discovered_meter.transport,
            )
            _LOGGER.debug(
                "Bluetooth GATT identity validation failed for serial=%s address=%s reason=%s chain=%s",
                discovered_meter.serial_number,
                discovered_meter.address,
                errors["base"],
                _exception_chain_summary(err),
            )
        except IneproIdentityError:
            _LOGGER.debug(
                "Bluetooth GATT identity validation failed: advertised serial %s does not match GATT serial",
                discovered_meter.serial_number,
            )
            errors["base"] = "invalid_identity"
        else:
            if gatt_serial is not None:
                entry_data[CONF_SERIAL_NUMBER] = gatt_serial
                gatt_validation_data[CONF_SERIAL_NUMBER] = gatt_serial
            validation_data = bluetooth_modbus_pairing_validation_data(entry_data)
            try:
                if discovered_meter.transport is not TransportType.BLUETOOTH:
                    await self._async_validate_modbus_config(validation_data)
                await self._async_validate_entry_identity(validation_data)
            except IneproBluetoothDeviceNotFound:
                errors["base"] = "bluetooth_device_not_found"
            except IneproConnectionError as err:
                reason = bluetooth_setup_identity_error_reason(
                    err,
                    discovered_meter.transport,
                )
                _LOGGER.debug(
                    "Bluetooth serial validation failed for serial=%s address=%s transport=%s reason=%s chain=%s",
                    discovered_meter.serial_number,
                    discovered_meter.address,
                    discovered_meter.transport.value,
                    reason,
                    _exception_chain_summary(err),
                )
                errors["base"] = reason
            except IneproIdentityError:
                _LOGGER.debug(
                    "ble_modbus_serial_validation_failed advertised_serial=%s",
                    discovered_meter.serial_number,
                )
                errors["base"] = "invalid_identity"
            else:
                _LOGGER.debug(
                    "ble_modbus_serial_validation_ok serial=%s address=%s",
                    discovered_meter.serial_number,
                    discovered_meter.address,
                )
                entry_data = with_routes_applied(
                    entry_data,
                    routes=(build_route_from_entry_data(entry_data),),
                )
                await self.async_set_unique_id(discovered_meter.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=discovered_meter.serial_number,
                    data=entry_data,
                )

        if step_id == "bluetooth_discovered":

            def schema_builder(values):
                return build_bluetooth_discovered_schema(
                    self._discovered_bluetooth_devices,
                    values,
                )
        else:
            schema_builder = build_bluetooth_confirm_schema

        description_placeholders = (
            {"count": str(len(self._discovered_bluetooth_devices))}
            if step_id == "bluetooth_discovered"
            else {
                CONF_NAME: discovered_meter.serial_number,
                "bluetooth_name": discovered_meter.bluetooth_name,
            }
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema_builder(user_input),
            description_placeholders=description_placeholders,
            errors=errors,
        )
