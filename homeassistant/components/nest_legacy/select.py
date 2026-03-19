"""Select platform for Nest."""

from __future__ import annotations

from dataclasses import dataclass

from bidict import bidict

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.enums import StructureMode
from .pynest.models import NestProtect, NestStructure

PARALLEL_UPDATES = 0

_BRIGHTNESS_BIDICT: bidict[int, str] = bidict({1: "low", 2: "medium", 3: "high"})


@dataclass(frozen=True, kw_only=True)
class NestProtectSelectEntityDescription(SelectEntityDescription):
    """Class to describe a Nest Protect select entity."""


@dataclass(frozen=True, kw_only=True)
class NestStructureSelectEntityDescription(SelectEntityDescription):
    """Class to describe a Nest Structure select entity."""


_PROTECT_DESCRIPTIONS: tuple[NestProtectSelectEntityDescription, ...] = (
    NestProtectSelectEntityDescription(
        key="night_light_brightness",
        translation_key="night_light_brightness",
        icon="mdi:lightbulb-on",
        options=[*_BRIGHTNESS_BIDICT.inverse],
        entity_category=EntityCategory.CONFIG,
    ),
)

_STRUCTURE_DESCRIPTIONS: tuple[NestStructureSelectEntityDescription, ...] = (
    NestStructureSelectEntityDescription(
        key="mode",
        translation_key="home_away_mode",
        icon="mdi:home-account",
        options=[e.value for e in StructureMode],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest Protect selects from a config entry."""
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [
        NestProtectSelect(coordinator, device, description)
        for device in coordinator.data.values()
        if isinstance(device, NestProtect)
        for description in _PROTECT_DESCRIPTIONS
        if getattr(device, description.key, None) is not None
    ]
    entities.extend(
        NestStructureSelect(coordinator, device, description)
        for device in coordinator.data.values()
        if isinstance(device, NestStructure)
        for description in _STRUCTURE_DESCRIPTIONS
    )
    async_add_devices(entities)


class NestProtectSelect(NestEntity[NestProtect], SelectEntity):
    """Representation of a Nest Protect Select."""

    entity_description: NestProtectSelectEntityDescription

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: NestProtect,
        description: NestProtectSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.serial_number}-{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option."""
        state = getattr(self.device, self.entity_description.key)
        return _BRIGHTNESS_BIDICT.get(state)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        brightness_level = _BRIGHTNESS_BIDICT.inverse.get(option)
        await self._set_device_data({self.entity_description.key: brightness_level})


class NestStructureSelect(NestEntity[NestStructure], SelectEntity):
    """Representation of a Nest Structure Select."""

    entity_description: NestStructureSelectEntityDescription
    _attr_name = None  # The select is the main feature of the device

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: NestStructure,
        description: NestStructureSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.serial_number}-{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option."""
        return self.device.mode.value

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._set_device_data({self.entity_description.key: option})
