"""Select platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

from pylamarzocco.const import (
    ModelName,
    PreExtractionMode,
    SmartStandByType,
    SteamTargetLevel,
    WidgetType,
)
from pylamarzocco.devices import LaMarzoccoMachine
from pylamarzocco.exceptions import RequestNotSuccessful
from pylamarzocco.models import PreBrewing, SteamBoilerLevel

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription

PARALLEL_UPDATES = 1

STEAM_LEVEL_HA_TO_LM = {
    "1": SteamTargetLevel.LEVEL_1,
    "2": SteamTargetLevel.LEVEL_2,
    "3": SteamTargetLevel.LEVEL_3,
}

STEAM_LEVEL_LM_TO_HA = {value: key for key, value in STEAM_LEVEL_HA_TO_LM.items()}

PREBREW_MODE_HA_TO_LM = {
    "disabled": PreExtractionMode.DISABLED,
    "prebrew": PreExtractionMode.PREBREWING,
    "preinfusion": PreExtractionMode.PREINFUSION,
}

PREBREW_MODE_LM_TO_HA = {value: key for key, value in PREBREW_MODE_HA_TO_LM.items()}

STANDBY_MODE_HA_TO_LM = {
    "power_on": SmartStandByType.POWER_ON,
    "last_brewing": SmartStandByType.LAST_BREW,
}

STANDBY_MODE_LM_TO_HA = {value: key for key, value in STANDBY_MODE_HA_TO_LM.items()}


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSelectEntityDescription(
    LaMarzoccoEntityDescription,
    SelectEntityDescription,
):
    """Description of a La Marzocco select entity."""

    current_option_fn: Callable[[LaMarzoccoMachine], str | None]
    select_option_fn: Callable[[LaMarzoccoMachine, str], Coroutine[Any, Any, bool]]


ENTITIES: tuple[LaMarzoccoSelectEntityDescription, ...] = (
    LaMarzoccoSelectEntityDescription(
        key="steam_temp_select",
        translation_key="steam_temp_select",
        options=["1", "2", "3"],
        select_option_fn=lambda machine, option: machine.set_steam_level(
            STEAM_LEVEL_HA_TO_LM[option]
        ),
        current_option_fn=lambda machine: STEAM_LEVEL_LM_TO_HA[
            cast(
                SteamBoilerLevel,
                machine.dashboard.config[WidgetType.CM_STEAM_BOILER_LEVEL],
            ).target_level
        ],
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (ModelName.LINEA_MINI_R, ModelName.LINEA_MICRA)
        ),
    ),
    LaMarzoccoSelectEntityDescription(
        key="prebrew_infusion_select",
        translation_key="prebrew_infusion_select",
        entity_category=EntityCategory.CONFIG,
        options=["disabled", "prebrew", "preinfusion"],
        select_option_fn=lambda machine, option: machine.set_pre_extraction_mode(
            PREBREW_MODE_HA_TO_LM[option]
        ),
        current_option_fn=lambda machine: PREBREW_MODE_LM_TO_HA[
            cast(PreBrewing, machine.dashboard.config[WidgetType.CM_PRE_BREWING]).mode
        ],
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (
                ModelName.LINEA_MICRA,
                ModelName.LINEA_MINI,
                ModelName.LINEA_MINI_R,
                ModelName.GS3_AV,
            )
        ),
    ),
    LaMarzoccoSelectEntityDescription(
        key="smart_standby_mode",
        translation_key="smart_standby_mode",
        entity_category=EntityCategory.CONFIG,
        options=["power_on", "last_brewing"],
        select_option_fn=lambda machine, option: machine.set_smart_standby(
            enabled=machine.schedule.smart_wake_up_sleep.smart_stand_by_enabled,
            mode=STANDBY_MODE_HA_TO_LM[option],
            minutes=machine.schedule.smart_wake_up_sleep.smart_stand_by_minutes,
        ),
        current_option_fn=lambda machine: STANDBY_MODE_LM_TO_HA[
            machine.schedule.smart_wake_up_sleep.smart_stand_by_after
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data.config_coordinator

    async_add_entities(
        LaMarzoccoSelectEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoSelectEntity(LaMarzoccoEntity, SelectEntity):
    """La Marzocco select entity."""

    entity_description: LaMarzoccoSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.entity_description.current_option_fn(self.coordinator.device)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option != self.current_option:
            try:
                await self.entity_description.select_option_fn(
                    self.coordinator.device, option
                )
            except RequestNotSuccessful as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="select_option_error",
                    translation_placeholders={
                        "key": self.entity_description.key,
                        "option": option,
                    },
                ) from exc
            self.async_write_ha_state()
