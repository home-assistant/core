"""Base entity for the LaMetric integration."""

from demetriek import Device

from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMetricAppsUpdateCoordinator, LaMetricDataUpdateCoordinator


def _device_info(data: Device, mac_fallback: str | None, host: str) -> DeviceInfo:
    """Build the device registry info from the reported device state."""
    # A device still connecting to its Wi-Fi leaves out its MAC and IP.
    wifi = data.wifi
    connections: set[tuple[str, str]] = set()
    if mac := wifi.mac or mac_fallback:
        connections.add((CONNECTION_NETWORK_MAC, mac))

    # A device without Bluetooth, like a SKY, reports no address.
    if (bluetooth := data.bluetooth) and bluetooth.address:
        connections.add((CONNECTION_BLUETOOTH, format_mac(bluetooth.address)))

    return DeviceInfo(
        connections=connections,
        identifiers={(DOMAIN, data.serial_number)},
        manufacturer="LaMetric Inc.",
        model=data.model_name,
        model_id=data.model,
        name=data.name,
        sw_version=data.os_version,
        serial_number=data.serial_number,
        configuration_url=f"https://{wifi.ip or host}/",
    )


class LaMetricEntity(CoordinatorEntity[LaMetricDataUpdateCoordinator]):
    """Defines a LaMetric entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LaMetricDataUpdateCoordinator) -> None:
        """Initialize the LaMetric entity."""
        super().__init__(coordinator=coordinator)

        # The device info is only registered at setup, so fall back to what
        # was stored then, rather than losing it until the next reload.
        self._attr_device_info = _device_info(
            coordinator.data,
            coordinator.config_entry.data.get(CONF_MAC),
            coordinator.lametric.host,
        )


class LaMetricAppsEntity(CoordinatorEntity[LaMetricAppsUpdateCoordinator]):
    """Defines a LaMetric entity based on the installed apps."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_coordinator: LaMetricDataUpdateCoordinator,
        coordinator: LaMetricAppsUpdateCoordinator,
    ) -> None:
        """Initialize the LaMetric apps entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = _device_info(
            device_coordinator.data,
            device_coordinator.config_entry.data.get(CONF_MAC),
            device_coordinator.lametric.host,
        )
