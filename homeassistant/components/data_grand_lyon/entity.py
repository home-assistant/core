"""Base entity for the Data Grand Lyon integration."""

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DataGrandLyonCoordinator


class DataGrandLyonEntity(CoordinatorEntity[DataGrandLyonCoordinator]):
    """Base entity for Data Grand Lyon."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataGrandLyonCoordinator,
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


class DataGrandLyonVelovEntity(DataGrandLyonEntity):
    """Base entity for Data Grand Lyon Vélo'v stations."""

    def __init__(
        self,
        coordinator: DataGrandLyonCoordinator,
        subentry: ConfigSubentry,
        description: EntityDescription,
    ) -> None:
        """Initialize the Vélo'v entity."""
        super().__init__(coordinator, subentry, description, "JCDecaux", "Station")

    @property
    def available(self) -> bool:
        """Return True if the station data is available."""
        return (
            super().available
            and self._subentry_id in self.coordinator.data.velov_stations
        )
