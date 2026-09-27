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
    coordinator_scan = config_entry.runtime_data.coordinator_scan

    assert config_entry.unique_id is not None

    async_add_entities(
        [LunatoneDALIScanStatus(coordinator_scan, config_entry.unique_id)]
    )


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
    ) -> None:
        """Initialize a Lunatone DALI scan status."""
        super().__init__(coordinator)

        self._config_entry_unique_id = config_entry_unique_id

        self._attr_unique_id = f"{config_entry_unique_id}-scan-progress"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._config_entry_unique_id)},
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the DALI scan is on."""
        return self.coordinator.data.busy
