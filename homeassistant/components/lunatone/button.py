"""Support for lunatone buttons."""

from typing import override

from lunatone_rest_api_client.models import StartScanData

from homeassistant.components.button import ButtonEntity
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
    """Set up the Lunatone Button platform."""
    coordinator_scan = config_entry.runtime_data.coordinator_scan

    assert config_entry.unique_id is not None

    async_add_entities(
        [DALIScanStartButtonEntity(coordinator_scan, config_entry.unique_id)]
    )


class DALIScanStartButtonEntity(
    CoordinatorEntity[LunatoneScanDataUpdateCoordinator], ButtonEntity
):
    """Representation of a DALI scan start button."""

    _attr_has_entity_name = True
    _attr_translation_key = "scan_start"

    def __init__(
        self,
        coordinator: LunatoneScanDataUpdateCoordinator,
        config_entry_unique_id: str,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator)
        self.entity_category = EntityCategory.CONFIG
        self._attr_unique_id = f"{config_entry_unique_id}-scan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry_unique_id)}
        )

    @override
    async def async_press(self) -> None:
        await self.coordinator.dali_scan_api.async_start(
            StartScanData(newInstallation=False, noAddressing=False)
        )
        await self.coordinator.async_request_refresh()
