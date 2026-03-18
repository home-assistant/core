"""Support for HomeWizard select platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.models import Batteries, CombinedModels as DeviceResponseEntry

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomeWizardConfigEntry, HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HomeWizardSelectEntityDescription(SelectEntityDescription):
    """Class describing HomeWizard select entities."""

    available_fn: Callable[[DeviceResponseEntry], bool]
    create_fn: Callable[[DeviceResponseEntry], bool]
    current_fn: Callable[[DeviceResponseEntry], str | None]
    set_fn: Callable[[HomeWizardEnergy, str], Awaitable[Any]]


DESCRIPTIONS = [
    HomeWizardSelectEntityDescription(
        key="battery_group_mode",
        translation_key="battery_group_mode",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=[Batteries.Mode.ZERO, Batteries.Mode.STANDBY, Batteries.Mode.TO_FULL],
        available_fn=lambda x: x.batteries is not None,
        create_fn=lambda x: x.batteries is not None,
        current_fn=lambda x: x.batteries.mode if x.batteries else None,
        set_fn=lambda api, mode: api.batteries(mode=Batteries.Mode(mode)),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeWizardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HomeWizard select based on a config entry."""
    async_add_entities(
        HomeWizardSelectEntity(
            coordinator=entry.runtime_data,
            description=description,
        )
        for description in DESCRIPTIONS
        if description.create_fn(entry.runtime_data.data)
    )


class HomeWizardSelectEntity(HomeWizardEntity, SelectEntity):
    """Defines a HomeWizard select entity."""

    entity_description: HomeWizardSelectEntityDescription

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        description: HomeWizardSelectEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.data)

    @homewizard_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_fn(self.coordinator.api, option)
        await self.coordinator.async_request_refresh()
