"""Support for lunatone buttons."""

from typing import Any, override

from lunatone_rest_api_client.models import StartScanData

from homeassistant.components.switch import SwitchEntity
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
        [DALIScanControlSwitchEntity(coordinator_scan, config_entry.unique_id)]
    )


class DALIScanControlSwitchEntity(
    CoordinatorEntity[LunatoneScanDataUpdateCoordinator], SwitchEntity
):
    """Representation of a DALI scan control switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "scan_control"

    def __init__(
        self,
        coordinator: LunatoneScanDataUpdateCoordinator,
        config_entry_unique_id: str,
    ) -> None:
        """Initialise the button."""
        super().__init__(coordinator)
        self.entity_category = EntityCategory.CONFIG
        self._attr_unique_id = f"{config_entry_unique_id}-scan-control"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry_unique_id)}
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return True if DALI scan is on."""
        return self.coordinator.data.busy

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.dali_scan_api.async_start(
            StartScanData(newInstallation=False, noAddressing=False)
        )
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.dali_scan_api.async_cancel()
        await self.coordinator.async_request_refresh()
