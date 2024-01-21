"""Switch platform for La Marzocco espresso machines."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSwitchEntityDescription(
    LaMarzoccoEntityDescription,
    SwitchEntityDescription,
):
    """Description of a La Marzocco Switch."""

    control_fn: Callable[[LaMarzoccoUpdateCoordinator, bool], Coroutine[Any, Any, bool]]
    is_on_fn: Callable[[LaMarzoccoUpdateCoordinator], bool]


ENTITIES: tuple[LaMarzoccoSwitchEntityDescription, ...] = (
    LaMarzoccoSwitchEntityDescription(
        key="main",
        name=None,
        control_fn=lambda coordinator, state: coordinator.lm.set_power(state),
        is_on_fn=lambda coordinator: coordinator.lm.current_status["power"],
    ),
    LaMarzoccoSwitchEntityDescription(
        key="auto_on_off",
        translation_key="auto_on_off",
        control_fn=lambda coordinator, state: coordinator.lm.set_auto_on_off_global(
            state
        ),
        is_on_fn=lambda coordinator: coordinator.lm.current_status["global_auto"]
        == "Enabled",
        entity_category=EntityCategory.CONFIG,
    ),
    LaMarzoccoSwitchEntityDescription(
        key="steam_boiler_enable",
        translation_key="steam_boiler",
        control_fn=lambda coordinator, state: coordinator.lm.set_steam(state),
        is_on_fn=lambda coordinator: coordinator.lm.current_status[
            "steam_boiler_enable"
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities and services."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        LaMarzoccoSwitchEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoSwitchEntity(LaMarzoccoEntity, SwitchEntity):
    """Switches representing espresso machine power, prebrew, and auto on/off."""

    entity_description: LaMarzoccoSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        await self.entity_description.control_fn(self.coordinator, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self.entity_description.control_fn(self.coordinator, False)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.is_on_fn(self.coordinator)
