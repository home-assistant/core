"""Common entity definitions."""

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WatercrystConfigEntry
from .const import DOMAIN
from .coordinator import (
    WatercrystMeasurementsCoordinator,
    WatercrystStateCoordinator,
    WatercrystUpdateCoordinator,
)


def _build_device_info(
    config_entry: WatercrystConfigEntry, coordinator: WatercrystUpdateCoordinator
) -> DeviceInfo:
    """Creates device info from the config entry and device meta data."""
    info = coordinator.data

    connections: set[tuple[str, str]] = set()

    if mac := info.system_mac_address:
        connections.add((CONNECTION_NETWORK_MAC, format_mac(mac)))

    return DeviceInfo(
        identifiers={(DOMAIN, info.biocat_serial)},
        connections=connections,
        manufacturer="WATERCryst",
        model=" ".join(part for part in (info.line, info.series) if part) or None,
        model_id=info.device_type_number,
        name=info.name or config_entry.title,
        serial_number=info.biocat_serial,
        sw_version=info.current_firmware_version,
        hw_version=info.current_hardware_version,
        configuration_url=f"https://app.watercryst.com/devices/{info.biocat_serial}",
    )


class WatercrystStateEntity(CoordinatorEntity[WatercrystStateCoordinator]):
    """WATERCryst state entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        coordinator: WatercrystUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a WatercrystStateEntity instance."""
        super().__init__(coordinator.state)
        self._attr_device_info = _build_device_info(config_entry, coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_{entity_description.key}"
        self.entity_description = entity_description


class WatercrystMeasurementsEntity(
    CoordinatorEntity[WatercrystMeasurementsCoordinator]
):
    """WATERCryst measurements entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        coordinator: WatercrystUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize a WatercrystMeasurementsEntity instance."""
        super().__init__(coordinator.measurements)
        self._attr_device_info = _build_device_info(config_entry, coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_{entity_description.key}"
        self.entity_description = entity_description
