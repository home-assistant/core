"""Platform for Miele vacuum integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import logging
from typing import Any, Final

from aiohttp import ClientResponseError
from pymiele import MieleEnum

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PROCESS_ACTION, PROGRAM_ID, MieleActions, MieleAppliance
from .coordinator import MieleConfigEntry
from .entity import MieleEntity

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)

# The following const classes define program speeds and programs for the vacuum cleaner.
# Miele have used the same and overlapping names for fan_speeds and programs even
# if the contexts are different. This is an attempt to make it clearer in the integration.


class FanSpeed(IntEnum):
    """Define fan speeds."""

    normal = 0
    turbo = 1
    silent = 2


class FanProgram(IntEnum):
    """Define fan programs."""

    auto = 1
    spot = 2
    turbo = 3
    silent = 4


PROGRAM_MAP = {
    "normal": FanProgram.auto,
    "turbo": FanProgram.turbo,
    "silent": FanProgram.silent,
}

PROGRAM_TO_SPEED: dict[int, str] = {
    FanProgram.auto: "normal",
    FanProgram.turbo: "turbo",
    FanProgram.silent: "silent",
    FanProgram.spot: "normal",
}


class MieleVacuumStateCode(MieleEnum):
    """Define vacuum state codes."""

    idle = 0
    cleaning = 5889
    returning = 5890
    paused = 5891
    going_to_target_area = 5892
    wheel_lifted = 5893
    dirty_sensors = 5894
    dust_box_missing = 5895
    blocked_drive_wheels = 5896
    blocked_brushes = 5897
    check_dust_box_and_filter = 5898
    internal_fault_reboot = 5899
    blocked_front_wheel = 5900
    docked = 5903, 5904
    remote_controlled = 5910
    unknown_code = -9999


SUPPORTED_FEATURES = (
    VacuumEntityFeature.STATE
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.CLEAN_SPOT
)


@dataclass(frozen=True, kw_only=True)
class MieleVacuumDescription(StateVacuumEntityDescription):
    """Class describing Miele vacuum entities."""

    on_value: int


@dataclass
class MieleVacuumDefinition:
    """Class for defining vacuum entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleVacuumDescription


VACUUM_TYPES: Final[tuple[MieleVacuumDefinition, ...]] = (
    MieleVacuumDefinition(
        types=(MieleAppliance.ROBOT_VACUUM_CLEANER,),
        description=MieleVacuumDescription(
            key="vacuum",
            on_value=14,
            name=None,
            translation_key="vacuum",
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the vacuum platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MieleVacuum(coordinator, device_id, definition.description)
        for device_id, device in coordinator.data.devices.items()
        for definition in VACUUM_TYPES
        if device.device_type in definition.types
    )


VACUUM_PHASE_TO_ACTIVITY = {
    MieleVacuumStateCode.idle: VacuumActivity.IDLE,
    MieleVacuumStateCode.docked: VacuumActivity.DOCKED,
    MieleVacuumStateCode.cleaning: VacuumActivity.CLEANING,
    MieleVacuumStateCode.going_to_target_area: VacuumActivity.CLEANING,
    MieleVacuumStateCode.returning: VacuumActivity.RETURNING,
    MieleVacuumStateCode.wheel_lifted: VacuumActivity.ERROR,
    MieleVacuumStateCode.dirty_sensors: VacuumActivity.ERROR,
    MieleVacuumStateCode.dust_box_missing: VacuumActivity.ERROR,
    MieleVacuumStateCode.blocked_drive_wheels: VacuumActivity.ERROR,
    MieleVacuumStateCode.blocked_brushes: VacuumActivity.ERROR,
    MieleVacuumStateCode.check_dust_box_and_filter: VacuumActivity.ERROR,
    MieleVacuumStateCode.internal_fault_reboot: VacuumActivity.ERROR,
    MieleVacuumStateCode.blocked_front_wheel: VacuumActivity.ERROR,
    MieleVacuumStateCode.paused: VacuumActivity.PAUSED,
    MieleVacuumStateCode.remote_controlled: VacuumActivity.PAUSED,
}


class MieleVacuum(MieleEntity, StateVacuumEntity):
    """Representation of a Vacuum entity."""

    entity_description: MieleVacuumDescription
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_fan_speed_list = [fan_speed.name for fan_speed in FanSpeed]
    _attr_name = None

    @property
    def activity(self) -> VacuumActivity | None:
        """Return activity."""
        return VACUUM_PHASE_TO_ACTIVITY.get(
            MieleVacuumStateCode(self.device.state_program_phase)
        )

    @property
    def battery_level(self) -> int | None:
        """Return the battery level."""
        return self.device.state_battery_level

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed."""
        return PROGRAM_TO_SPEED.get(self.device.state_program_id)

    @property
    def available(self) -> bool:
        """Return the availability of the entity."""

        return (
            self.action.power_off_enabled or self.action.power_on_enabled
        ) and super().available

    async def send(self, device_id: str, action: dict[str, Any]) -> None:
        """Send action to the device."""
        try:
            await self.api.send_action(device_id, action)
        except ClientResponseError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_state_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from ex

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Clean spot."""
        await self.send(self._device_id, {PROGRAM_ID: FanProgram.spot})

    async def async_start(self, **kwargs: Any) -> None:
        """Start cleaning."""
        await self.send(self._device_id, {PROCESS_ACTION: MieleActions.START})

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop cleaning."""
        await self.send(self._device_id, {PROCESS_ACTION: MieleActions.STOP})

    async def async_pause(self, **kwargs: Any) -> None:
        """Pause cleaning."""
        await self.send(self._device_id, {PROCESS_ACTION: MieleActions.PAUSE})

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self.send(self._device_id, {PROGRAM_ID: PROGRAM_MAP[fan_speed]})
