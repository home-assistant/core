"""Support for lunatone selects."""

from enum import StrEnum
from typing import Final, override

from lunatone_rest_api_client.models import StartScanData

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry, LunatoneScanDataUpdateCoordinator


class DALIScanMethod(StrEnum):
    """DALI device scan methods."""

    NONE = "none"
    CURRENT_DEVICE_LIST = "current_device_list"
    SYSTEM_EXTENSION = "system_extension"
    NEW_INSTALLATION = "new_installation"


DALI_SCAN_ENTITY = SelectEntityDescription(
    key="dali_scan",
    translation_key="dali_scan",
    options=[option.value for option in DALIScanMethod],
)
DEFAULT_DALI_SCAN_METHOD: Final = str(DALIScanMethod.NONE)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lunatone Select platform."""
    coordinator_scan = config_entry.runtime_data.coordinator_scan

    assert config_entry.unique_id is not None

    async_add_entities([DALIScanSelectEntity(coordinator_scan, config_entry.unique_id)])


class DALIScanSelectEntity(
    CoordinatorEntity[LunatoneScanDataUpdateCoordinator], SelectEntity
):
    """Representation of a DALI scan select."""

    entity_description = DALI_SCAN_ENTITY

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LunatoneScanDataUpdateCoordinator,
        config_entry_unique_id: str,
    ) -> None:
        """Initialise the select."""
        super().__init__(coordinator)
        self.entity_category = EntityCategory.CONFIG
        self._attr_unique_id = f"{config_entry_unique_id}-scan"
        self._attr_current_option = DEFAULT_DALI_SCAN_METHOD
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry_unique_id)}
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return (
            str(DALIScanMethod.NONE)
            if not self.coordinator.data.busy
            else self._attr_current_option
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Select light color mode."""
        self._attr_current_option = option
        match self._attr_current_option:
            case DALIScanMethod.CURRENT_DEVICE_LIST:
                data = StartScanData(newInstallation=False, noAddressing=True)
            case DALIScanMethod.SYSTEM_EXTENSION:
                data = StartScanData(newInstallation=False, noAddressing=False)
            case DALIScanMethod.NEW_INSTALLATION:
                data = StartScanData(newInstallation=True, noAddressing=False)
            case _:
                return

        await self.coordinator.dali_scan_api.async_start(data)
        await self.coordinator.async_request_refresh()
