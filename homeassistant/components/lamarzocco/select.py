"""Select platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pylamarzocco.const import (
    MachineModel,
    PhysicalKey,
    PrebrewMode,
    SmartStandbyMode,
    SteamLevel,
)
from pylamarzocco.devices.machine import LaMarzoccoMachine
from pylamarzocco.exceptions import RequestNotSuccessful
from pylamarzocco.models import LaMarzoccoMachineConfig

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription, LaMarzoccScaleEntity

PARALLEL_UPDATES = 1

STEAM_LEVEL_HA_TO_LM = {
    "1": SteamLevel.LEVEL_1,
    "2": SteamLevel.LEVEL_2,
    "3": SteamLevel.LEVEL_3,
}

STEAM_LEVEL_LM_TO_HA = {value: key for key, value in STEAM_LEVEL_HA_TO_LM.items()}

PREBREW_MODE_HA_TO_LM = {
    "disabled": PrebrewMode.DISABLED,
    "prebrew": PrebrewMode.PREBREW,
    "prebrew_enabled": PrebrewMode.PREBREW_ENABLED,
    "preinfusion": PrebrewMode.PREINFUSION,
}

PREBREW_MODE_LM_TO_HA = {value: key for key, value in PREBREW_MODE_HA_TO_LM.items()}

STANDBY_MODE_HA_TO_LM = {
    "power_on": SmartStandbyMode.POWER_ON,
    "last_brewing": SmartStandbyMode.LAST_BREWING,
}

STANDBY_MODE_LM_TO_HA = {value: key for key, value in STANDBY_MODE_HA_TO_LM.items()}


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSelectEntityDescription(
    LaMarzoccoEntityDescription,
    SelectEntityDescription,
):
    """Description of a La Marzocco select entity."""

    current_option_fn: Callable[[LaMarzoccoMachineConfig], str | None]
    select_option_fn: Callable[[LaMarzoccoMachine, str], Coroutine[Any, Any, bool]]


ENTITIES: tuple[LaMarzoccoSelectEntityDescription, ...] = (
    LaMarzoccoSelectEntityDescription(
        key="steam_temp_select",
        translation_key="steam_temp_select",
        options=["1", "2", "3"],
        select_option_fn=lambda machine, option: machine.set_steam_level(
            STEAM_LEVEL_HA_TO_LM[option]
        ),
        current_option_fn=lambda config: STEAM_LEVEL_LM_TO_HA[config.steam_level],
        supported_fn=lambda coordinator: coordinator.device.model
        == MachineModel.LINEA_MICRA,
    ),
    LaMarzoccoSelectEntityDescription(
        key="prebrew_infusion_select",
        translation_key="prebrew_infusion_select",
        entity_category=EntityCategory.CONFIG,
        options=["disabled", "prebrew", "preinfusion"],
        select_option_fn=lambda machine, option: machine.set_prebrew_mode(
            PREBREW_MODE_HA_TO_LM[option]
        ),
        current_option_fn=lambda config: PREBREW_MODE_LM_TO_HA[config.prebrew_mode],
        supported_fn=lambda coordinator: coordinator.device.model
        in (
            MachineModel.GS3_AV,
            MachineModel.LINEA_MICRA,
            MachineModel.LINEA_MINI,
            MachineModel.LINEA_MINI_R,
        ),
    ),
    LaMarzoccoSelectEntityDescription(
        key="smart_standby_mode",
        translation_key="smart_standby_mode",
        entity_category=EntityCategory.CONFIG,
        options=["power_on", "last_brewing"],
        select_option_fn=lambda machine, option: machine.set_smart_standby(
            enabled=machine.config.smart_standby.enabled,
            mode=STANDBY_MODE_HA_TO_LM[option],
            minutes=machine.config.smart_standby.minutes,
        ),
        current_option_fn=lambda config: STANDBY_MODE_LM_TO_HA[
            config.smart_standby.mode
        ],
    ),
)

SCALE_ENTITIES: tuple[LaMarzoccoSelectEntityDescription, ...] = (
    LaMarzoccoSelectEntityDescription(
        key="active_bbw",
        translation_key="active_bbw",
        options=["a", "b"],
        select_option_fn=lambda machine, option: machine.set_active_bbw_recipe(
            PhysicalKey[option.upper()]
        ),
        current_option_fn=lambda config: (
            config.bbw_settings.active_dose.name.lower()
            if config.bbw_settings
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data.config_coordinator

    entities = [
        LaMarzoccoSelectEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    ]

    if (
        coordinator.device.model in (MachineModel.LINEA_MINI, MachineModel.LINEA_MINI_R)
        and coordinator.device.config.scale
    ):
        entities.extend(
            LaMarzoccoScaleSelectEntity(coordinator, description)
            for description in SCALE_ENTITIES
        )

    def _async_add_new_scale() -> None:
        async_add_entities(
            LaMarzoccoScaleSelectEntity(coordinator, description)
            for description in SCALE_ENTITIES
        )

    coordinator.new_device_callback.append(_async_add_new_scale)

    async_add_entities(entities)


class LaMarzoccoSelectEntity(LaMarzoccoEntity, SelectEntity):
    """La Marzocco select entity."""

    entity_description: LaMarzoccoSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return str(
            self.entity_description.current_option_fn(self.coordinator.device.config)
        )

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


class LaMarzoccoScaleSelectEntity(LaMarzoccoSelectEntity, LaMarzoccScaleEntity):
    """Select entity for La Marzocco scales."""

    entity_description: LaMarzoccoSelectEntityDescription
