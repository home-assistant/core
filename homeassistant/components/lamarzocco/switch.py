"""Switch platform for La Marzocco espresso machines."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

from pylamarzocco import LaMarzoccoMachine
from pylamarzocco.const import MachineMode, ModelName, WidgetType
from pylamarzocco.exceptions import RequestNotSuccessful
from pylamarzocco.models import (
    MachineStatus,
    SteamBoilerLevel,
    SteamBoilerTemperature,
    WakeUpScheduleSettings,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry, LaMarzoccoUpdateCoordinator
from .entity import LaMarzoccoBaseEntity, LaMarzoccoEntity, LaMarzoccoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSwitchEntityDescription(
    LaMarzoccoEntityDescription,
    SwitchEntityDescription,
):
    """Description of a La Marzocco Switch."""

    control_fn: Callable[[LaMarzoccoMachine, bool], Coroutine[Any, Any, bool]]
    is_on_fn: Callable[[LaMarzoccoMachine], bool]


ENTITIES: tuple[LaMarzoccoSwitchEntityDescription, ...] = (
    LaMarzoccoSwitchEntityDescription(
        key="main",
        translation_key="main",
        name=None,
        control_fn=lambda machine, state: machine.set_power(state),
        is_on_fn=(
            lambda machine: cast(
                MachineStatus, machine.dashboard.config[WidgetType.CM_MACHINE_STATUS]
            ).mode
            is MachineMode.BREWING_MODE
        ),
    ),
    LaMarzoccoSwitchEntityDescription(
        key="steam_boiler_enable",
        translation_key="steam_boiler",
        control_fn=lambda machine, state: machine.set_steam(state),
        is_on_fn=(
            lambda machine: cast(
                SteamBoilerLevel,
                machine.dashboard.config[WidgetType.CM_STEAM_BOILER_LEVEL],
            ).enabled
        ),
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            in (ModelName.LINEA_MINI_R, ModelName.LINEA_MICRA)
        ),
    ),
    LaMarzoccoSwitchEntityDescription(
        key="steam_boiler_enable",
        translation_key="steam_boiler",
        control_fn=lambda machine, state: machine.set_steam(state),
        is_on_fn=(
            lambda machine: cast(
                SteamBoilerTemperature,
                machine.dashboard.config[WidgetType.CM_STEAM_BOILER_TEMPERATURE],
            ).enabled
        ),
        supported_fn=(
            lambda coordinator: coordinator.device.dashboard.model_name
            not in (ModelName.LINEA_MINI_R, ModelName.LINEA_MICRA)
        ),
    ),
    LaMarzoccoSwitchEntityDescription(
        key="smart_standby_enabled",
        translation_key="smart_standby_enabled",
        entity_category=EntityCategory.CONFIG,
        control_fn=lambda machine, state: machine.set_smart_standby(
            enabled=state,
            mode=machine.schedule.smart_wake_up_sleep.smart_stand_by_after,
            minutes=machine.schedule.smart_wake_up_sleep.smart_stand_by_minutes,
        ),
        is_on_fn=lambda machine: machine.schedule.smart_wake_up_sleep.smart_stand_by_enabled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities and services."""

    coordinator = entry.runtime_data.config_coordinator

    entities: list[SwitchEntity] = []
    entities.extend(
        LaMarzoccoSwitchEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )

    entities.extend(
        LaMarzoccoAutoOnOffSwitchEntity(coordinator, wake_up_sleep_entry)
        for wake_up_sleep_entry in coordinator.device.schedule.smart_wake_up_sleep.schedules
    )

    async_add_entities(entities)


class LaMarzoccoSwitchEntity(LaMarzoccoEntity, SwitchEntity):
    """Switches representing espresso machine power, prebrew, and auto on/off."""

    entity_description: LaMarzoccoSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        try:
            await self.entity_description.control_fn(self.coordinator.device, True)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_on_error",
                translation_placeholders={"key": self.entity_description.key},
            ) from exc
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        try:
            await self.entity_description.control_fn(self.coordinator.device, False)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_off_error",
                translation_placeholders={"key": self.entity_description.key},
            ) from exc
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.entity_description.is_on_fn(self.coordinator.device)


class LaMarzoccoAutoOnOffSwitchEntity(LaMarzoccoBaseEntity, SwitchEntity):
    """Switch representing espresso machine auto on/off."""

    coordinator: LaMarzoccoUpdateCoordinator
    _attr_translation_key = "auto_on_off"

    def __init__(
        self,
        coordinator: LaMarzoccoUpdateCoordinator,
        schedule_entry: WakeUpScheduleSettings,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, f"auto_on_off_{schedule_entry.identifier}")
        assert schedule_entry.identifier
        self._schedule_entry = schedule_entry
        self._identifier = schedule_entry.identifier
        self._attr_translation_placeholders = {"id": schedule_entry.identifier}
        self._attr_entity_category = EntityCategory.CONFIG

    async def _async_enable(self, state: bool) -> None:
        """Enable or disable the auto on/off schedule."""
        self._schedule_entry.enabled = state
        try:
            await self.coordinator.device.set_wakeup_schedule(self._schedule_entry)
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auto_on_off_error",
                translation_placeholders={"id": self._identifier, "state": str(state)},
            ) from exc
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self._async_enable(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self._async_enable(False)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._schedule_entry.enabled
