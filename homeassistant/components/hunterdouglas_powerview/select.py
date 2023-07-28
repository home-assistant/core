"""Support for hunterdouglass_powerview settings."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Final

from aiopvapi.helpers.constants import ATTR_NAME, FUNCTION_SET_POWER
from aiopvapi.resources.shade import BaseShade

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewDeviceInfo, PowerviewEntryData

_LOGGER = logging.getLogger(__name__)


@dataclass
class PowerviewSelectDescriptionMixin:
    """Mixin to describe a select entity."""

    current_fn: Callable[[BaseShade], Any]
    select_fn: Callable[[BaseShade, str], Coroutine[Any, Any, bool]]
    create_entity_fn: Callable[[BaseShade], bool]
    options_fn: Callable[[BaseShade], list[str]]


@dataclass
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
        current_fn=lambda shade: shade.get_power_source(),
        options_fn=lambda shade: shade.supported_power_sources(),
        select_fn=lambda shade, option: shade.set_power_source(option),
        create_entity_fn=lambda shade: shade.is_supported(FUNCTION_SET_POWER),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas select entities."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    entities: list[PowerViewSelect] = []
    for shade in pv_entry.shade_data.values():
        if shade.has_battery_info() is True:
            room_name = getattr(pv_entry.room_data.get(shade.room_id), ATTR_NAME, "")
            for description in DROPDOWNS:
                if description.create_entity_fn(shade):
                    entities.append(
                        PowerViewSelect(
                            pv_entry.coordinator,
                            pv_entry.device_info,
                            room_name,
                            shade,
                            shade.name,
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

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.entity_description.options_fn(self._shade)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self._shade, option)
        await self._shade.refresh()  # force update data to ensure new info is in coordinator
        self.async_write_ha_state()
