"""Select platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lmcloud.const import MachineModel, PrebrewMode, SteamLevel
from lmcloud.lm_machine import LaMarzoccoMachine

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoMachineUpdateCoordinator
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription

PBREWBREW_MODE_HA_TO_LM = {
    "disabled": PrebrewMode.DISABLED,
    "prebrew": PrebrewMode.PREBREW,
    "typeb": PrebrewMode.PREINFUSION,
}


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSelectEntityDescription(
    LaMarzoccoEntityDescription,
    SelectEntityDescription,
):
    """Description of a La Marzocco select entity."""

    current_option_fn: Callable[[LaMarzoccoMachine], str]
    select_option_fn: Callable[
        [LaMarzoccoMachineUpdateCoordinator, str], Coroutine[Any, Any, bool]
    ]


ENTITIES: tuple[LaMarzoccoSelectEntityDescription, ...] = (
    LaMarzoccoSelectEntityDescription(
        key="steam_temp_select",
        translation_key="steam_temp_select",
        options=["126", "128", "131"],
        select_option_fn=lambda coordinator, option: coordinator.device.set_steam_level(
            SteamLevel(int(option))
        ),
        current_option_fn=lambda device: str(device.steam_level),
        supported_fn=lambda coordinator: coordinator.device.model
        == MachineModel.LINEA_MICRA,
    ),
    LaMarzoccoSelectEntityDescription(
        key="prebrew_infusion_select",
        translation_key="prebrew_infusion_select",
        options=["disabled", "prebrew", "typeb"],
        select_option_fn=lambda coordinator,
        option: coordinator.device.set_prebrew_mode(PBREWBREW_MODE_HA_TO_LM[option]),
        current_option_fn=lambda device: device.config.prebrew_mode.lower(),
        supported_fn=lambda coordinator: coordinator.device.model
        in (
            MachineModel.GS3_AV,
            MachineModel.LINEA_MICRA,
            MachineModel.LINEA_MINI,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LaMarzoccoSelectEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoSelectEntity(LaMarzoccoEntity, SelectEntity):
    """La Marzocco select entity."""

    entity_description: LaMarzoccoSelectEntityDescription

    @property
    def current_option(self) -> str:
        """Return the current selected option."""
        return str(self.entity_description.current_option_fn(self.coordinator.device))

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option != self.current_option:
            await self.entity_description.select_option_fn(self.coordinator, option)
            self.async_write_ha_state()
