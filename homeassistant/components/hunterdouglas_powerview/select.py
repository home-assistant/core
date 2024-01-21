"""Support for hunterdouglass_powerview settings."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Final

from aiopvapi.resources.shade import BaseShade, factory as PvShade

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_KIND,
    DOMAIN,
    POWER_SUPPLY_TYPE_MAP,
    POWER_SUPPLY_TYPE_REVERSE_MAP,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_BATTERY_LEVEL,
)
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewDeviceInfo, PowerviewEntryData


@dataclass(frozen=True)
class PowerviewSelectDescriptionMixin:
    """Mixin to describe a select entity."""

    current_fn: Callable[[BaseShade], Any]
    select_fn: Callable[[BaseShade, str], Coroutine[Any, Any, bool]]


@dataclass(frozen=True)
class PowerviewSelectDescription(
    SelectEntityDescription, PowerviewSelectDescriptionMixin
):
    """A class that describes select entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG


DROPDOWNS: Final = [
    PowerviewSelectDescription(
        key="powersource",
        translation_key="power_source",
        icon="mdi:power-plug-outline",
        current_fn=lambda shade: POWER_SUPPLY_TYPE_MAP.get(
            shade.raw_data.get(ATTR_BATTERY_KIND), None
        ),
        options=list(POWER_SUPPLY_TYPE_MAP.values()),
        select_fn=lambda shade, option: shade.set_power_source(
            POWER_SUPPLY_TYPE_REVERSE_MAP.get(option)
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas select entities."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for raw_shade in pv_entry.shade_data.values():
        shade: BaseShade = PvShade(raw_shade, pv_entry.api)
        if SHADE_BATTERY_LEVEL not in shade.raw_data:
            continue
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = pv_entry.room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")

        for description in DROPDOWNS:
            entities.append(
                PowerViewSelect(
                    pv_entry.coordinator,
                    pv_entry.device_info,
                    room_name,
                    shade,
                    name_before_refresh,
                    description,
                )
            )

    async_add_entities(entities)


class PowerViewSelect(ShadeEntity, SelectEntity):
    """Representation of a select entity."""

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
        description: PowerviewSelectDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self.entity_description: PowerviewSelectDescription = description
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self._shade)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self._shade, option)
        # force update data to ensure new info is in coordinator
        await self._shade.refresh()
        self.async_write_ha_state()
