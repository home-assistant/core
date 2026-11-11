"""Base entity for Sofar devices."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from sofar_modbus.modern.battery_pack import BatteryPack

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVED_COMPONENTS
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData

# A part of the inverter, as (device translation key, number).
type SofarPart = tuple[str, int]


@dataclass(frozen=True, kw_only=True)
class SofarEntityDescription(EntityDescription):
    """Describe a Sofar entity."""

    component: str  # attribute name on SofarInverter, e.g. 'grid', 'pv_1_2'
    part: SofarPart | None = None  # None keeps the entity on the inverter


def entity_unique_id(serial: str, key: str) -> str:
    """Name an entity by the inverter's serial and its key."""
    return f"{serial}_{key}"


def battery_pack_identifier(serial: str, pack: BatteryPack) -> str:
    """Name the device of one BTS battery pack by its group and place."""
    return f"{serial}_battery_pack_{pack.group_nr}_{pack.pack_nr}"


@callback
def async_remove_unserved_entities(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    platform: Platform,
    descriptions: Iterable[SofarEntityDescription],
) -> None:
    """Drop entities the inverter does not serve, so they don't linger."""
    # Without a stored set, served is only a guess from the type.
    if SERVED_COMPONENTS not in entry.data:
        return
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    registry = er.async_get(hass)
    for description in descriptions:
        if description.component in entry.runtime_data.served_components:
            continue
        if (
            entity_id := registry.async_get_entity_id(
                platform, DOMAIN, entity_unique_id(entry.unique_id, description.key)
            )
        ) is not None:
            registry.async_remove(entity_id)


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
        self._attr_unique_id = self._unique_id(serial)
        self._attr_device_info = self._device_info(runtime_data, serial)

    def _unique_id(self, serial: str) -> str:
        """Name the entity by the inverter's serial and its key."""
        return entity_unique_id(serial, self.entity_description.key)

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
        if not super().available or self.coordinator.data is None:
            return False
        # Setup may drop a component a night setup created entities for.
        return (
            self.entity_description.component
            in self.coordinator.device.expected_components
            and self.entity_description.component not in self.coordinator.data.failed
        )
