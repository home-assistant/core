"""Creates HomeWizard Energy switch entities."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homewizard_energy import HomeWizardEnergy

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DeviceResponseEntry
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler


@dataclass
class HomeWizardEntityDescriptionMixin:
    """Mixin values for HomeWizard entities."""

    create_fn: Callable[[HWEnergyDeviceUpdateCoordinator], bool]
    available_fn: Callable[[DeviceResponseEntry], bool]
    is_on_fn: Callable[[DeviceResponseEntry], bool | None]
    set_fn: Callable[[HomeWizardEnergy, bool], Awaitable[Any]]


@dataclass
class HomeWizardSwitchEntityDescription(
    SwitchEntityDescription, HomeWizardEntityDescriptionMixin
):
    """Class describing HomeWizard switch entities."""

    icon_off: str | None = None


SWITCHES = [
    HomeWizardSwitchEntityDescription(
        key="power_on",
        device_class=SwitchDeviceClass.OUTLET,
        create_fn=lambda coordinator: coordinator.supports_state(),
        available_fn=lambda data: data.state is not None and not data.state.switch_lock,
        is_on_fn=lambda data: data.state.power_on if data.state else None,
        set_fn=lambda api, active: api.state_set(power_on=active),
    ),
    HomeWizardSwitchEntityDescription(
        key="switch_lock",
        name="Switch lock",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:lock",
        icon_off="mdi:lock-open",
        create_fn=lambda coordinator: coordinator.supports_state(),
        available_fn=lambda data: data.state is not None,
        is_on_fn=lambda data: data.state.switch_lock if data.state else None,
        set_fn=lambda api, active: api.state_set(switch_lock=active),
    ),
    HomeWizardSwitchEntityDescription(
        key="cloud_connection",
        name="Cloud connection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:cloud",
        icon_off="mdi:cloud-off-outline",
        create_fn=lambda coordinator: coordinator.supports_system(),
        available_fn=lambda data: data.system is not None,
        is_on_fn=lambda data: data.system.cloud_enabled if data.system else None,
        set_fn=lambda api, active: api.system_set(cloud_enabled=active),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        HomeWizardSwitchEntity(
            coordinator=coordinator,
            description=description,
            entry=entry,
        )
        for description in SWITCHES
        if description.create_fn(coordinator)
    )


class HomeWizardSwitchEntity(HomeWizardEntity, SwitchEntity):
    """Representation of a HomeWizard switch."""

    entity_description: HomeWizardSwitchEntityDescription

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        description: HomeWizardSwitchEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if self.entity_description.icon_off and self.is_on is False:
            return self.entity_description.icon_off
        return super().icon

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
