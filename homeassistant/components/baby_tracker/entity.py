"""Base entities for Baby Tracker (Nighp)."""

from typing import override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BabyData, BabyTrackerCoordinator

MANUFACTURER = "Nighp"
BABY_MODEL = "Baby Tracker"


class BabyTrackerEntity(CoordinatorEntity[BabyTrackerCoordinator]):
    """Base class for every Baby Tracker entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BabyTrackerCoordinator,
        description: EntityDescription,
        scope_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """Set up an entity on a device, with a unique ID scoped to that device's owner."""
        super().__init__(coordinator)
        self.entity_description = description
        # The scope (a baby's ID, or the entry's ID) and then the entity's key.
        self._attr_unique_id = f"{scope_id}_{description.key}"
        self._attr_device_info = device_info


class BabyTrackerBabyEntity(BabyTrackerEntity):
    """An entity on a baby's device, built from that baby's data."""

    def __init__(
        self,
        coordinator: BabyTrackerCoordinator,
        description: EntityDescription,
        baby_id: str,
    ) -> None:
        """Set up an entity for one baby."""
        info = DeviceInfo(
            identifiers={(DOMAIN, baby_id)},
            manufacturer=MANUFACTURER,
            model=BABY_MODEL,
            entry_type=DeviceEntryType.SERVICE,
        )
        if name := coordinator.data.babies[baby_id].name:
            info["name"] = name
        else:
            info["translation_key"] = "baby"
        super().__init__(coordinator, description, baby_id, info)
        self._baby_id = baby_id

    @property
    def _baby(self) -> BabyData | None:
        return self.coordinator.data.babies.get(self._baby_id)

    @property
    @override
    def available(self) -> bool:
        """Return whether the baby is on the account."""
        return super().available and self._baby is not None
