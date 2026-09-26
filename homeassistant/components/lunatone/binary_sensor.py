"""Platform for Lunatone binary sensor integration."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry, LunatoneScanDataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lunatone binary sensors from the config entry."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_scan = config_entry.runtime_data.coordinator_scan

    assert config_entry.unique_id is not None

    entities: list[BinarySensorEntity] = [
        LunatoneDALIScanStatus(coordinator_scan, config_entry.unique_id)
    ]
    entities.extend(
        [
            LunatoneDALIScanStatus(
                coordinator_scan, config_entry.unique_id, int(line_id)
            )
            for line_id in coordinator_info.data.lines
        ]
    )

    async_add_entities(entities)


class LunatoneDALIScanStatus(
    CoordinatorEntity[LunatoneScanDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Lunatone DALI scan status."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "scan_status"

    def __init__(
        self,
        coordinator: LunatoneScanDataUpdateCoordinator,
        config_entry_unique_id: str,
        line: int | None = None,
    ) -> None:
        """Initialize a Lunatone DALI scan status."""
        super().__init__(coordinator)

        self._line = line

        device_unique_id = config_entry_unique_id
        if line is not None:
            device_unique_id += f"-line{line}"

        self._attr_unique_id = f"{device_unique_id}-scan-progress"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the DALI scan is on."""
        if self._line is not None:
            for line_status in self.coordinator.data.lines:
                if line_status.line == self._line:
                    return line_status.busy
            return False
        return self.coordinator.data.busy
