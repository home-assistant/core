"""Base entity for the Data Grand Lyon integration."""

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import DataGrandLyonTclCoordinator, DataGrandLyonVelovCoordinator


class DataGrandLyonEntity[_CoordinatorT: DataUpdateCoordinator](
    CoordinatorEntity[_CoordinatorT]
):
    """Base entity for Data Grand Lyon."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: _CoordinatorT,
        subentry: ConfigSubentry,
        description: EntityDescription,
        manufacturer: str,
        model: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._subentry_id = subentry.subentry_id
        assert subentry.unique_id is not None

        self._attr_unique_id = f"{subentry.unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.unique_id)},
            name=subentry.title,
            manufacturer=manufacturer,
            model=model,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return True if subentry data is available."""
        return super().available and self._subentry_id in self.coordinator.data


class DataGrandLyonTclEntity(DataGrandLyonEntity[DataGrandLyonTclCoordinator]):
    """Base entity for Data Grand Lyon TCL stops."""

    def __init__(
        self,
        coordinator: DataGrandLyonTclCoordinator,
        subentry: ConfigSubentry,
        description: EntityDescription,
    ) -> None:
        """Initialize the TCL entity."""
        super().__init__(coordinator, subentry, description, "TCL", "Stop")


class DataGrandLyonVelovEntity(DataGrandLyonEntity[DataGrandLyonVelovCoordinator]):
    """Base entity for Data Grand Lyon Vélo'v stations."""

    def __init__(
        self,
        coordinator: DataGrandLyonVelovCoordinator,
        subentry: ConfigSubentry,
        description: EntityDescription,
    ) -> None:
        """Initialize the Vélo'v entity."""
        super().__init__(coordinator, subentry, description, "JCDecaux", "Station")
