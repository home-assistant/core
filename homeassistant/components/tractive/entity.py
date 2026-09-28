"""A entity class for Tractive integration."""

from aiotractive import PetStatus, Trackable, TrackerStatus

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TractiveCoordinator


class TractiveEntity(CoordinatorEntity[TractiveCoordinator]):
    """Tractive entity class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TractiveCoordinator,
        trackable: Trackable,
        hardware_entity: bool = True,
    ) -> None:
        """Initialize tracker entity."""
        super().__init__(coordinator)
        self._pet_id = trackable.pet_id
        self._tracker_id = trackable.tracker_id
        if hardware_entity:
            self._attr_device_info = DeviceInfo(
                configuration_url="https://my.tractive.com/",
                identifiers={(DOMAIN, trackable.tracker_id)},
                translation_key="tracker",
                translation_placeholders={"id": trackable.tracker_id},
                manufacturer="Tractive GmbH",
                sw_version=trackable.tracker_details["fw_version"],
                model_id=trackable.tracker_details["model_number"],
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, trackable.pet_id)},
                name=trackable.name,
                via_device_id=dr.async_get_device_id_by_identifier(
                    coordinator.hass,
                    (DOMAIN, trackable.tracker_id),
                    config_entry_id=coordinator.config_entry.entry_id,
                ),
                entry_type=DeviceEntryType.SERVICE,
            )

    @property
    def _tracker_status(self) -> TrackerStatus:
        """Return the live status of the tracker."""
        return self.coordinator.data.trackers[self._tracker_id]

    @property
    def _pet_status(self) -> PetStatus:
        """Return the live status of the pet."""
        # Pets without health data have no status entry until the first event
        return self.coordinator.data.pets.get(self._pet_id, PetStatus())
