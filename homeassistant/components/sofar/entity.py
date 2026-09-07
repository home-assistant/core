"""Base entity for Sofar devices."""

from dataclasses import dataclass
from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SofarDataUpdateCoordinator, SofarRuntimeData

# A part of the inverter, as (device translation key, number).
type SofarPart = tuple[str, int]


@dataclass(frozen=True, kw_only=True)
class SofarEntityDescription(EntityDescription):
    """Describe a Sofar entity."""

    component: str  # attribute name on SofarInverter, e.g. 'grid', 'pv_1_2'
    part: SofarPart | None = None  # None keeps the entity on the inverter


class SofarEntity(CoordinatorEntity[SofarDataUpdateCoordinator]):
    """Defines a base Sofar entity."""

    _attr_has_entity_name = True
    entity_description: SofarEntityDescription

    def __init__(
        self,
        runtime_data: SofarRuntimeData,
        entity_description: SofarEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data.coordinator_for(entity_description.component))
        self.entity_description = entity_description
        serial = self.coordinator.device.serial_number
        assert serial is not None
        self._attr_unique_id = f"{serial}_{entity_description.key}"
        self._attr_device_info = self._device_info(runtime_data, serial)

    def _device_info(
        self, runtime_data: SofarRuntimeData, serial: str
    ) -> dr.DeviceInfo:
        """Place the entity on the inverter, or on the part it measures."""
        if (part := self.entity_description.part) is None:
            return self.coordinator.device_info
        kind, number = part
        return dr.DeviceInfo(
            identifiers={(DOMAIN, f"{serial}_{kind}_{number}")},
            via_device_id=runtime_data.inverter_device_id,
            translation_key=kind,
            translation_placeholders={"number": str(number)},
        )

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available:
            return False
        return self.entity_description.component not in self.coordinator.data.failed
