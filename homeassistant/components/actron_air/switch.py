"""Switch platform for Actron Air integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator
from .entity import ActronAirAcEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ActronAirSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Actron Air switch entities."""

    is_on_fn: Callable[[ActronAirSystemCoordinator], bool]
    set_fn: Callable[[ActronAirSystemCoordinator, bool], Awaitable[None]]
    is_supported_fn: Callable[[ActronAirSystemCoordinator], bool] = lambda _: True


SWITCHES: tuple[ActronAirSwitchEntityDescription, ...] = (
    ActronAirSwitchEntityDescription(
        key="away_mode",
        translation_key="away_mode",
        is_on_fn=lambda coordinator: coordinator.data.user_aircon_settings.away_mode,
        set_fn=lambda coordinator,
        enabled: coordinator.data.user_aircon_settings.set_away_mode(enabled),
    ),
    ActronAirSwitchEntityDescription(
        key="continuous_fan",
        translation_key="continuous_fan",
        is_on_fn=lambda coordinator: coordinator.data.user_aircon_settings.continuous_fan_enabled,
        set_fn=lambda coordinator,
        enabled: coordinator.data.user_aircon_settings.set_continuous_mode(enabled),
    ),
    ActronAirSwitchEntityDescription(
        key="quiet_mode",
        translation_key="quiet_mode",
        is_on_fn=lambda coordinator: coordinator.data.user_aircon_settings.quiet_mode_enabled,
        set_fn=lambda coordinator,
        enabled: coordinator.data.user_aircon_settings.set_quiet_mode(enabled),
    ),
    ActronAirSwitchEntityDescription(
        key="turbo_mode",
        translation_key="turbo_mode",
        is_on_fn=lambda coordinator: coordinator.data.user_aircon_settings.turbo_enabled,
        set_fn=lambda coordinator,
        enabled: coordinator.data.user_aircon_settings.set_turbo_mode(enabled),
        is_supported_fn=lambda coordinator: coordinator.data.user_aircon_settings.turbo_supported,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air switch entities."""
    system_coordinators = entry.runtime_data.system_coordinators
    async_add_entities(
        ActronAirSwitch(coordinator, description)
        for coordinator in system_coordinators.values()
        for description in SWITCHES
        if description.is_supported_fn(coordinator)
    )


class ActronAirSwitch(ActronAirAcEntity, SwitchEntity):
    """Actron Air switch."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: ActronAirSwitchEntityDescription

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        description: ActronAirSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.entity_description.is_on_fn(self.coordinator)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.coordinator, False)
