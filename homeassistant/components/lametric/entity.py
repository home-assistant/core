"""Base entity for the LaMetric integration."""

from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator


class LaMetricEntity(CoordinatorEntity[LaMetricDataUpdateCoordinator]):
    """Defines a LaMetric entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LaMetricDataUpdateCoordinator) -> None:
        """Initialize the LaMetric entity."""
        super().__init__(coordinator=coordinator)

        # A device still connecting to its Wi-Fi leaves out its MAC and IP.
        # The device info is only registered at setup, so fall back to what
        # was stored then, rather than losing them until the next reload.
        wifi = coordinator.data.wifi
        connections: set[tuple[str, str]] = set()
        if mac := wifi.mac or coordinator.config_entry.data.get(CONF_MAC):
            connections.add((CONNECTION_NETWORK_MAC, mac))

        # A device without Bluetooth, like a SKY, reports no address.
        if (bluetooth := coordinator.data.bluetooth) and bluetooth.address:
            connections.add((CONNECTION_BLUETOOTH, format_mac(bluetooth.address)))

        self._attr_device_info = DeviceInfo(
            connections=connections,
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            manufacturer="LaMetric Inc.",
            model=coordinator.data.model_name,
            model_id=coordinator.data.model,
            name=coordinator.data.name,
            sw_version=coordinator.data.os_version,
            serial_number=coordinator.data.serial_number,
            configuration_url=f"https://{wifi.ip or coordinator.lametric.host}/",
        )
