"""Support for hunterdouglas_powerview numbers."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from aiopvapi.helpers.constants import ATTR_NAME, MOTION_VELOCITY
from aiopvapi.resources.shade import BaseShade, ShadePosition

from homeassistant.components.number import (
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewConfigEntry, PowerviewDeviceInfo


@dataclass(frozen=True, kw_only=True)
class PowerviewNumberDescription(NumberEntityDescription):
    """Class to describe a Number entity."""

    create_entity_fn: Callable[[BaseShade], bool]
    store_value_fn: Callable[[PowerviewShadeUpdateCoordinator, int, float | None], None]
    entity_category: EntityCategory = EntityCategory.CONFIG


def store_velocity(
    coordinator: PowerviewShadeUpdateCoordinator,
    shade_id: int,
    value: float | None,
) -> None:
    """Store the desired shade velocity in the coordinator."""
    coordinator.data.update_shade_velocity(shade_id, ShadePosition(velocity=value))


NUMBERS: Final = (
    PowerviewNumberDescription(
        key="velocity",
        name="Velocity",
        mode=NumberMode.SLIDER,
        icon="mdi:speedometer",
        create_entity_fn=lambda shade: shade.is_supported(MOTION_VELOCITY),
        store_value_fn=store_velocity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the hunter douglas number entities."""
    pv_entry = entry.runtime_data
    entities: list[PowerViewNumber] = []
    for shade in pv_entry.shade_data.values():
        room_name = getattr(pv_entry.room_data.get(shade.room_id), ATTR_NAME, "")
        entities.extend(
            PowerViewNumber(
                pv_entry.coordinator,
                pv_entry.device_info,
                room_name,
                shade,
                shade.name,
                description,
            )
            for description in NUMBERS
            if description.create_entity_fn(shade)
        )
    async_add_entities(entities)


class PowerViewNumber(ShadeEntity, RestoreNumber):
    """Representation of a number entity."""

    entity_description: PowerviewNumberDescription

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
        description: PowerviewNumberDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self.entity_description = description
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.entity_description.store_value_fn(self.coordinator, self._shade.id, value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        last_number_data = await self.async_get_last_number_data()
        value = last_number_data.native_value if last_number_data is not None else 0
        self._attr_native_value = value
        self.entity_description.store_value_fn(self.coordinator, self._shade.id, value)
