"""Creates HomeWizard Energy switch entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.models import CombinedModels as DeviceResponseEntry

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeWizardConfigEntry
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HomeWizardSwitchEntityDescription(SwitchEntityDescription):
    """Class describing HomeWizard switch entities."""

    available_fn: Callable[[DeviceResponseEntry], bool]
    create_fn: Callable[[DeviceResponseEntry], bool]
    is_on_fn: Callable[[DeviceResponseEntry], bool | None]
    set_fn: Callable[[HomeWizardEnergy, bool], Awaitable[Any]]


SWITCHES = [
    HomeWizardSwitchEntityDescription(
        key="power_on",
        name=None,
        device_class=SwitchDeviceClass.OUTLET,
        create_fn=lambda x: x.device.supports_state(),
        available_fn=lambda x: x.state is not None and not x.state.switch_lock,
        is_on_fn=lambda x: x.state.power_on if x.state else None,
        set_fn=lambda api, active: api.state(power_on=active),
    ),
    HomeWizardSwitchEntityDescription(
        key="switch_lock",
        translation_key="switch_lock",
        entity_category=EntityCategory.CONFIG,
        create_fn=lambda x: x.device.supports_state(),
        available_fn=lambda x: x.state is not None,
        is_on_fn=lambda x: x.state.switch_lock if x.state else None,
        set_fn=lambda api, active: api.state(switch_lock=active),
    ),
    HomeWizardSwitchEntityDescription(
        key="cloud_connection",
        translation_key="cloud_connection",
        entity_category=EntityCategory.CONFIG,
        create_fn=lambda _: True,
        available_fn=lambda x: x.system is not None,
        is_on_fn=lambda x: x.system.cloud_enabled if x.system else None,
        set_fn=lambda api, active: api.system(cloud_enabled=active),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeWizardConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    async_add_entities(
        HomeWizardSwitchEntity(entry.runtime_data, description)
        for description in SWITCHES
        if description.create_fn(entry.runtime_data.data)
    )


class HomeWizardSwitchEntity(HomeWizardEntity, SwitchEntity):
    """Representation of a HomeWizard switch."""

    entity_description: HomeWizardSwitchEntityDescription

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        description: HomeWizardSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    def is_on(self) -> bool | None:
        """Return state of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @homewizard_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.coordinator.api, True)
        await self.coordinator.async_refresh()

    @homewizard_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.coordinator.api, False)
        await self.coordinator.async_refresh()
