"""Support for Litter-Robot "Vacuum"."""
from __future__ import annotations

from datetime import time
from typing import Any

from pylitterbot import LitterRobot
from pylitterbot.enums import LitterBoxStatus
import voluptuous as vol

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_PAUSED,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .entity import LitterRobotEntity
from .hub import LitterRobotHub

SERVICE_SET_SLEEP_MODE = "set_sleep_mode"

LITTER_BOX_STATUS_STATE_MAP = {
    LitterBoxStatus.CLEAN_CYCLE: STATE_CLEANING,
    LitterBoxStatus.EMPTY_CYCLE: STATE_CLEANING,
    LitterBoxStatus.CLEAN_CYCLE_COMPLETE: STATE_DOCKED,
    LitterBoxStatus.CAT_SENSOR_TIMING: STATE_DOCKED,
    LitterBoxStatus.DRAWER_FULL_1: STATE_DOCKED,
    LitterBoxStatus.DRAWER_FULL_2: STATE_DOCKED,
    LitterBoxStatus.READY: STATE_DOCKED,
    LitterBoxStatus.CAT_SENSOR_INTERRUPTED: STATE_PAUSED,
    LitterBoxStatus.OFF: STATE_OFF,
}

LITTER_BOX_ENTITY = StateVacuumEntityDescription(
    "litter_box", translation_key="litter_box"
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LitterRobotCleaner(robot=robot, hub=hub, description=LITTER_BOX_ENTITY)
        for robot in hub.litter_robots()
    ]
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SLEEP_MODE,
        {
            vol.Required("enabled"): cv.boolean,
            vol.Optional("start_time"): cv.time,
        },
        "async_set_sleep_mode",
    )


class LitterRobotCleaner(LitterRobotEntity[LitterRobot], StateVacuumEntity):
    """Litter-Robot "Vacuum" Cleaner."""

    _attr_supported_features = (
        VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.TURN_OFF
        | VacuumEntityFeature.TURN_ON
    )

    @property
    def state(self) -> str:
        """Return the state of the cleaner."""
        return LITTER_BOX_STATUS_STATE_MAP.get(self.robot.status, STATE_ERROR)

    @property
    def status(self) -> str:
        """Return the status of the cleaner."""
        return (
            f"{self.robot.status.text}{' (Sleeping)' if self.robot.is_sleeping else ''}"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the cleaner on, starting a clean cycle."""
        await self.robot.set_power_status(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the unit off, stopping any cleaning in progress as is."""
        await self.robot.set_power_status(False)

    async def async_start(self) -> None:
        """Start a clean cycle."""
        await self.robot.start_cleaning()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self.robot.set_power_status(False)

    async def async_set_sleep_mode(
        self, enabled: bool, start_time: str | None = None
    ) -> None:
        """Set the sleep mode."""
        await self.robot.set_sleep_mode(
            enabled, self.parse_time_at_default_timezone(start_time)
        )

    @staticmethod
    def parse_time_at_default_timezone(time_str: str | None) -> time | None:
        """Parse a time string and add default timezone."""
        if time_str is None:
            return None

        if (parsed_time := dt_util.parse_time(time_str)) is None:
            return None

        return (
            dt_util.start_of_local_day()
            .replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=parsed_time.second,
            )
            .timetz()
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "is_sleeping": self.robot.is_sleeping,
            "sleep_mode_enabled": self.robot.sleep_mode_enabled,
            "power_status": self.robot.power_status,
            "status": self.status,
        }
