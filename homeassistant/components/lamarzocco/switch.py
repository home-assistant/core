"""Switch platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lmcloud.const import BoilerType
from lmcloud.lm_machine import LaMarzoccoMachine
from lmcloud.models import LaMarzoccoMachineConfig

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSwitchEntityDescription(
    LaMarzoccoEntityDescription,
    SwitchEntityDescription,
):
    """Description of a La Marzocco Switch."""

    control_fn: Callable[[LaMarzoccoMachine, bool], Coroutine[Any, Any, bool]]
    is_on_fn: Callable[[LaMarzoccoMachineConfig], bool]


ENTITIES: tuple[LaMarzoccoSwitchEntityDescription, ...] = (
    LaMarzoccoSwitchEntityDescription(
        key="main",
        translation_key="main",
        name=None,
        control_fn=lambda machine, state: machine.set_power(state),
        is_on_fn=lambda config: config.turned_on,
    ),
    LaMarzoccoSwitchEntityDescription(
        key="steam_boiler_enable",
        translation_key="steam_boiler",
        control_fn=lambda machine, state: machine.set_steam(state),
        is_on_fn=lambda config: config.boilers[BoilerType.STEAM].enabled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities and services."""

    coordinator = entry.runtime_data
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
        await self.entity_description.control_fn(self.coordinator.device, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self.entity_description.control_fn(self.coordinator.device, False)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.is_on_fn(self.coordinator.device.config)
