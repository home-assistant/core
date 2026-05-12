"""Shared Modbus bus helpers used by the Inepro Metering config and options flows."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.data_entry_flow import FlowResult

from .config_flow_shared import CONFIG_ENTRY_VERSION, discovered_meter_key
from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_FAMILY,
    CONF_METERS,
    CONF_PARITY,
    CONF_SERIAL_NUMBER,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_TRANSPORT,
    CONF_VARIANT,
    DOMAIN,
    MeterFamily,
    TransportType,
)
from .discovery import DiscoveredGrowMeter
from .entry_data import (
    ConfiguredMeter,
    build_bus_unique_id,
    ensure_bus_meter_routes,
    get_bus_route_for_meter,
    get_configured_meters,
    serialize_configured_meter,
)


def _meter_serials(
    meters: tuple[ConfiguredMeter, ...] | list[ConfiguredMeter],
) -> set[str]:
    """Return known physical serial numbers from configured meters."""
    return {meter.serial_number for meter in meters if meter.serial_number}


class SerialBusFlowMixin:
    """Helpers for shared-bus-backed config flow steps."""

    def _filter_new_bus_devices(
        self,
        discovered_devices: tuple[DiscoveredGrowMeter, ...],
        *,
        connection_data: dict[str, Any],
        transport: TransportType,
    ) -> tuple[DiscoveredGrowMeter, ...]:
        """Filter out already configured shared-bus devices."""
        configured_slave_ids: set[int] = set()
        configured_serials = self._configured_meter_serials()

        config_entry = getattr(self, "_config_entry", None)
        if config_entry is not None:
            configured_slave_ids = {
                get_bus_route_for_meter(
                    meter,
                    bus_entry_data=config_entry.data,
                ).slave_id
                for meter in get_configured_meters(
                    config_entry.data,
                    title=config_entry.title,
                )
            }
        else:
            existing_entry = self._find_existing_bus_entry(
                connection_data,
                transport=transport,
            )
            if existing_entry is not None:
                configured_slave_ids = {
                    get_bus_route_for_meter(
                        meter,
                        bus_entry_data=existing_entry.data,
                    ).slave_id
                    for meter in get_configured_meters(
                        existing_entry.data,
                        title=existing_entry.title,
                    )
                }

        return tuple(
            discovered_meter
            for discovered_meter in discovered_devices
            if discovered_meter.slave_id not in configured_slave_ids
            and discovered_meter.serial_number not in configured_serials
        )

    def _filter_new_serial_devices(
        self,
        discovered_devices: tuple[DiscoveredGrowMeter, ...],
    ) -> tuple[DiscoveredGrowMeter, ...]:
        """Filter out already configured serial bus devices."""
        return self._filter_new_bus_devices(
            discovered_devices,
            connection_data=self._bus_scan_connection,
            transport=self._bus_scan_transport or TransportType.SERIAL,
        )

    def _get_discovered_meters(
        self,
        selected_keys: str | list[str],
    ) -> tuple[DiscoveredGrowMeter, ...]:
        """Return the previously discovered meters matching the selected keys."""
        normalized_keys = (
            {selected_keys} if isinstance(selected_keys, str) else set(selected_keys)
        )
        selected = [
            discovered_meter
            for discovered_meter in self._discovered_bus_devices
            if discovered_meter_key(discovered_meter) in normalized_keys
        ]

        if not selected or len(selected) != len(normalized_keys):
            raise ValueError(f"Unknown discovered meter selection: {selected_keys}")

        return tuple(selected)

    def _find_existing_bus_entry(
        self,
        connection_data: dict[str, Any],
        *,
        transport: TransportType,
    ) -> ConfigEntry | None:
        """Return the existing shared-bus entry for one endpoint, if any."""
        target_unique_id = build_bus_unique_id(
            {
                CONF_TRANSPORT: transport.value,
                **connection_data,
            }
        )
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if TransportType(entry.data[CONF_TRANSPORT]) is not transport:
                continue
            if CONF_METERS not in entry.data:
                continue
            if build_bus_unique_id(entry.data) == target_unique_id:
                return entry
        return None

    def _find_existing_serial_entry(
        self,
        connection_data: dict[str, Any],
    ) -> ConfigEntry | None:
        """Return the existing serial entry for one bus endpoint, if any."""
        return self._find_existing_bus_entry(
            connection_data,
            transport=TransportType.SERIAL,
        )

    def _configured_meter_serials(
        self,
        *,
        exclude_entry: ConfigEntry | None = None,
    ) -> set[str]:
        """Return physical meter serials already configured in Home Assistant."""
        configured_serials: set[str] = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if exclude_entry is not None and entry.entry_id == exclude_entry.entry_id:
                continue
            configured_serials.update(
                _meter_serials(get_configured_meters(entry.data, title=entry.title))
            )
        return configured_serials

    async def _async_upsert_bus(
        self,
        connection_data: dict[str, Any],
        *,
        transport: TransportType,
        meters: tuple[ConfiguredMeter, ...],
        scan_interval: int,
    ) -> FlowResult:
        """Create or append to one shared Modbus bus entry."""
        existing_entry = self._find_existing_bus_entry(
            connection_data,
            transport=transport,
        )

        bus_entry_data = {
            CONF_TRANSPORT: transport.value,
            **connection_data,
        }

        if existing_entry is None:
            configured_serials = self._configured_meter_serials()
            meters = tuple(
                meter
                for meter in meters
                if meter.serial_number is None
                or meter.serial_number not in configured_serials
            )
            if not meters and transport is not TransportType.TCP_GATEWAY:
                return self.async_abort(reason="already_configured")

            configured_meters = [
                ensure_bus_meter_routes(meter, bus_entry_data=bus_entry_data)
                for meter in meters
            ]
            entry_family = self._meter_selection.get(
                CONF_FAMILY,
                configured_meters[0].family
                if configured_meters
                else MeterFamily.GROW.value,
            )
            entry_data = {
                CONF_FAMILY: entry_family,
                CONF_SCAN_INTERVAL: scan_interval,
                **bus_entry_data,
                CONF_METERS: [
                    serialize_configured_meter(meter) for meter in configured_meters
                ],
            }
            await self.async_set_unique_id(build_bus_unique_id(entry_data))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=(
                    configured_meters[0].name
                    if configured_meters
                    else self._gateway_bus_title(entry_data)
                ),
                data=entry_data,
            )

        existing_meters = list(
            get_configured_meters(existing_entry.data, title=existing_entry.title)
        )
        existing_slave_ids = {
            get_bus_route_for_meter(
                meter,
                bus_entry_data=existing_entry.data,
            ).slave_id
            for meter in existing_meters
        }
        existing_serials = _meter_serials(
            existing_meters
        ) | self._configured_meter_serials(
            exclude_entry=existing_entry,
        )
        new_meters = [
            ensure_bus_meter_routes(
                meter,
                bus_entry_data=existing_entry.data,
            )
            for meter in meters
            if meter.slave_id not in existing_slave_ids
            and (
                meter.serial_number is None
                or meter.serial_number not in existing_serials
            )
        ]
        if not new_meters:
            return self.async_abort(reason="already_configured")

        merged_meters = [
            serialize_configured_meter(
                ensure_bus_meter_routes(
                    meter,
                    bus_entry_data=existing_entry.data,
                )
            )
            for meter in (*existing_meters, *new_meters)
        ]
        new_data = {
            key: value
            for key, value in existing_entry.data.items()
            if key not in {CONF_VARIANT, CONF_SLAVE_ID}
        }
        new_data.update(
            {
                **bus_entry_data,
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_METERS: merged_meters,
            }
        )
        self.hass.config_entries.async_update_entry(
            existing_entry,
            data=new_data,
            version=CONFIG_ENTRY_VERSION,
        )
        await self.hass.config_entries.async_reload(existing_entry.entry_id)
        return self.async_abort(reason="meter_added_to_existing_bus")

    async def _async_upsert_serial_bus(
        self,
        connection_data: dict[str, Any],
        *,
        meters: tuple[ConfiguredMeter, ...],
        scan_interval: int,
    ) -> FlowResult:
        """Create a new serial bus entry or append meters to an existing bus entry."""
        return await self._async_upsert_bus(
            connection_data,
            transport=TransportType.SERIAL,
            meters=meters,
            scan_interval=scan_interval,
        )

    async def _async_upsert_tcp_gateway_bus(
        self,
        connection_data: dict[str, Any],
        *,
        meters: tuple[ConfiguredMeter, ...],
        scan_interval: int,
    ) -> FlowResult:
        """Create a new TCP gateway bus entry or append meters to an existing one."""
        return await self._async_upsert_bus(
            connection_data,
            transport=TransportType.TCP_GATEWAY,
            meters=meters,
            scan_interval=scan_interval,
        )

    def _gateway_bus_title(self, entry_data: dict[str, Any]) -> str:
        """Return a clear title for a gateway-only shared-bus entry."""
        if TransportType(entry_data[CONF_TRANSPORT]) is TransportType.TCP_GATEWAY:
            endpoint = f"{entry_data[CONF_HOST]}:{entry_data[CONF_PORT]}"
            serial_number = str(entry_data.get(CONF_SERIAL_NUMBER, "")).strip()
            if serial_number:
                return f"Inepro Gateway {serial_number}"
            return f"Inepro Gateway {endpoint}"
        return "Inepro Modbus bus"

    @property
    def _bus_connection_data(self) -> dict[str, Any]:
        """Return the current shared-bus transport settings from the config entry."""
        transport = TransportType(self._config_entry.data[CONF_TRANSPORT])
        if transport is TransportType.SERIAL:
            return {
                CONF_TRANSPORT: TransportType.SERIAL.value,
                CONF_SERIAL_PORT: self._config_entry.data[CONF_SERIAL_PORT],
                CONF_BAUDRATE: self._config_entry.data[CONF_BAUDRATE],
                CONF_BYTESIZE: self._config_entry.data[CONF_BYTESIZE],
                CONF_PARITY: self._config_entry.data[CONF_PARITY],
                CONF_STOPBITS: self._config_entry.data[CONF_STOPBITS],
                CONF_TIMEOUT: self._config_entry.data[CONF_TIMEOUT],
            }

        return {
            CONF_TRANSPORT: transport.value,
            CONF_HOST: self._config_entry.data[CONF_HOST],
            CONF_PORT: self._config_entry.data[CONF_PORT],
            CONF_TIMEOUT: self._config_entry.data[CONF_TIMEOUT],
        }

    @property
    def _serial_connection_data(self) -> dict[str, Any]:
        """Return the current serial transport settings from the config entry."""
        return self._bus_connection_data

    @property
    def _configured_meters(self) -> tuple[ConfiguredMeter, ...]:
        """Return the meters configured under this entry."""
        return get_configured_meters(
            self._config_entry.data,
            title=self._config_entry.title,
        )
