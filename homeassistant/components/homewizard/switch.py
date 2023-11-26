"""Creates HomeWizard Energy switch entities."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DeviceResponseEntry
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity
from .helpers import homewizard_exception_handler


async def _async_power_on_state_set_with_possible_lock(
    coordinator: HWEnergyDeviceUpdateCoordinator, state: bool
) -> None:
    """Set the power state of the device, taking into account the switch lock.

    Trying to set a locked switch will raise an exception.
    """
    if coordinator.data.state and coordinator.data.state.switch_lock:
        raise ServiceValidationError(
            "Could not change state; Lock is active",
            translation_domain=DOMAIN,
            translation_key="switch_locked",
        )
    await coordinator.api.state_set(power_on=state)


@dataclass(kw_only=True)
class HomeWizardSwitchEntityDescription(SwitchEntityDescription):
    """Class describing HomeWizard switch entities."""

    available_fn: Callable[[DeviceResponseEntry], bool]
    create_fn: Callable[[HWEnergyDeviceUpdateCoordinator], bool]
    icon_off: str | None = None
    is_on_fn: Callable[[DeviceResponseEntry], bool | None]
    set_fn: Callable[[HWEnergyDeviceUpdateCoordinator, bool], Awaitable[Any]]


SWITCHES = [
    HomeWizardSwitchEntityDescription(
        key="power_on",
        name=None,
        device_class=SwitchDeviceClass.OUTLET,
        create_fn=lambda coordinator: coordinator.supports_state(),
        available_fn=lambda data: data.state is not None,
        is_on_fn=lambda data: data.state.power_on if data.state else None,
        set_fn=_async_power_on_state_set_with_possible_lock,
    ),
    HomeWizardSwitchEntityDescription(
        key="switch_lock",
        translation_key="switch_lock",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:lock",
        icon_off="mdi:lock-open",
        create_fn=lambda coordinator: coordinator.supports_state(),
        available_fn=lambda data: data.state is not None,
        is_on_fn=lambda data: data.state.switch_lock if data.state else None,
        set_fn=lambda coordinator, active: coordinator.api.state_set(
            switch_lock=active
        ),
    ),
    HomeWizardSwitchEntityDescription(
        key="cloud_connection",
        translation_key="cloud_connection",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:cloud",
        icon_off="mdi:cloud-off-outline",
        create_fn=lambda coordinator: coordinator.supports_system(),
        available_fn=lambda data: data.system is not None,
        is_on_fn=lambda data: data.system.cloud_enabled if data.system else None,
        set_fn=lambda coordinator, active: coordinator.api.system_set(
            cloud_enabled=active
        ),
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
        HomeWizardSwitchEntity(coordinator, description)
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
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

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
        await self.entity_description.set_fn(self.coordinator, True)
        await self.coordinator.async_refresh()

    @homewizard_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.coordinator, False)
        await self.coordinator.async_refresh()
