"""Shared HA helpers for TCP gateway configuration entities."""

from inepro_metering.gateway_settings import (
    GatewaySettingState,
    supports_gateway_management,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL_NUMBER, CONF_TRANSPORT, MANUFACTURER, TransportType
from .coordinator import (
    CoordinatorData,
    IneproMeteringCoordinator,
    IneproSerialBusCoordinator,
    SerialBusCoordinatorData,
)
from .device_identity import gateway_device_identifier, gateway_serial_number

GatewayCoordinator = IneproMeteringCoordinator | IneproSerialBusCoordinator
GatewayCoordinatorData = CoordinatorData | SerialBusCoordinatorData


def entry_supports_gateway_management(entry: ConfigEntry) -> bool:
    """Return whether one config entry reaches the TCP gateway management plane."""
    return supports_gateway_management(TransportType(entry.data[CONF_TRANSPORT]))


def downstream_meter_via_device(entry: ConfigEntry) -> tuple[str, str] | None:
    """Return the parent gateway identifier for downstream TCP-gateway meters."""
    if not entry_supports_gateway_management(entry):
        return None
    return gateway_device_identifier(entry)


def gateway_display_name(entry: ConfigEntry, *, gateway=None) -> str:
    """Return the standard user-facing gateway hub/device name."""
    serial_number = None
    if gateway is not None and gateway.serial_number:
        serial_number = gateway.serial_number
    else:
        stored_serial = entry.data.get(CONF_SERIAL_NUMBER)
        if isinstance(stored_serial, str) and stored_serial.strip():
            serial_number = stored_serial.strip()

    endpoint = f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
    if serial_number:
        return f"Inepro Gateway {serial_number}"
    return f"Inepro Gateway {endpoint}"


def build_gateway_device_info(
    entry: ConfigEntry,
    *,
    name: str,
    gateway,
) -> DeviceInfo:
    """Return a device-registry view for one TCP gateway endpoint."""
    return DeviceInfo(
        identifiers={gateway_device_identifier(entry, gateway=gateway)},
        manufacturer=MANUFACTURER,
        model=(
            "TCP Gateway"
            if gateway is None or gateway.device_type is None
            else gateway.device_type
        ),
        name=gateway_display_name(entry, gateway=gateway),
        configuration_url="https://www.ineprometering.com/",
        serial_number=gateway_serial_number(entry, gateway),
        sw_version=None if gateway is None else gateway.firmware_version,
        hw_version=None if gateway is None else gateway.hardware_version,
    )


class IneproGatewayEntity(CoordinatorEntity[GatewayCoordinator]):
    """Shared base entity for gateway-bound configuration entities."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GatewayCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the shared gateway entity base."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def _gateway_data(self) -> GatewayCoordinatorData | None:
        """Return the latest coordinator data regardless of entry shape."""
        return self.coordinator.data

    @property
    def gateway(self):
        """Return the latest gateway metadata."""
        data = self._gateway_data
        return None if data is None else data.gateway

    @property
    def gateway_settings(self) -> dict[str, GatewaySettingState]:
        """Return the latest decoded gateway setting states."""
        data = self._gateway_data
        return {} if data is None else data.gateway_settings

    def gateway_setting_state(self, key: str) -> GatewaySettingState | None:
        """Return one decoded gateway setting state by key."""
        return self.gateway_settings.get(key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the gateway device information."""
        return build_gateway_device_info(
            self._entry,
            name=f"{self._entry.title} Gateway",
            gateway=self.gateway,
        )
