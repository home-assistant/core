"""The Elexa Guardian integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GuardianConfigEntry
from .const import API_SYSTEM_DIAGNOSTICS, CONF_UID, DOMAIN
from .coordinator import GuardianDataUpdateCoordinator


class GuardianEntity(CoordinatorEntity[GuardianDataUpdateCoordinator]):
    """Define a base Guardian entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: GuardianDataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.entity_description = description


class PairedSensorEntity(GuardianEntity):
    """Define a Guardian paired sensor entity."""

    def __init__(
        self,
        entry: GuardianConfigEntry,
        coordinator: GuardianDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)

        paired_sensor_uid = coordinator.data["uid"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, paired_sensor_uid)},
            manufacturer="Elexa",
            model=coordinator.data["codename"],
            name=f"Guardian paired sensor {paired_sensor_uid}",
            via_device=(DOMAIN, entry.data[CONF_UID]),
        )
        self._attr_unique_id = f"{paired_sensor_uid}_{description.key}"


@dataclass(frozen=True, kw_only=True)
class ValveControllerEntityDescription(EntityDescription):
    """Describe a Guardian valve controller entity."""

    api_category: str


class ValveControllerEntity(GuardianEntity):
    """Define a Guardian valve controller entity."""

    def __init__(
        self,
        entry: GuardianConfigEntry,
        coordinators: dict[str, GuardianDataUpdateCoordinator],
        description: ValveControllerEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinators[description.api_category], description)

        self._diagnostics_coordinator = coordinators[API_SYSTEM_DIAGNOSTICS]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_UID])},
            manufacturer="Elexa",
            model=self._diagnostics_coordinator.data["firmware"],
            name=f"Guardian valve controller {entry.data[CONF_UID]}",
        )
        self._attr_unique_id = f"{entry.data[CONF_UID]}_{description.key}"
