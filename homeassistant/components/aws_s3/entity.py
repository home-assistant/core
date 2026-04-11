"""Define the AWS S3 entity."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BUCKET, DOMAIN
from .coordinator import S3DataUpdateCoordinator


class S3Entity(CoordinatorEntity[S3DataUpdateCoordinator]):
    """Defines a base AWS S3 entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: S3DataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize an AWS S3 entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this AWS S3 device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=f"Bucket {self.coordinator.config_entry.data[CONF_BUCKET]}",
            manufacturer="AWS",
            model="AWS S3",
            entry_type=DeviceEntryType.SERVICE,
        )
