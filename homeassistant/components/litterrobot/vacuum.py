"""Support for Litter-Robot "Vacuum"."""
from __future__ import annotations

from typing import Any

from pylitterbot.enums import LitterBoxStatus
from pylitterbot.robot import VALID_WAIT_TIMES
import voluptuous as vol

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_PAUSED,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STATUS,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    VacuumEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotControlEntity
from .hub import LitterRobotHub

SUPPORT_LITTERROBOT = (
    SUPPORT_START | SUPPORT_STATE | SUPPORT_STATUS | SUPPORT_TURN_OFF | SUPPORT_TURN_ON
)
TYPE_LITTER_BOX = "Litter Box"

SERVICE_RESET_WASTE_DRAWER = "reset_waste_drawer"
SERVICE_SET_SLEEP_MODE = "set_sleep_mode"
SERVICE_SET_WAIT_TIME = "set_wait_time"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for robot in hub.account.robots:
        entities.append(
            LitterRobotCleaner(robot=robot, entity_type=TYPE_LITTER_BOX, hub=hub)
        )

    async_add_entities(entities, True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RESET_WASTE_DRAWER,
        {},
        "async_reset_waste_drawer",
    )
    platform.async_register_entity_service(
        SERVICE_SET_SLEEP_MODE,
        {
            vol.Required("enabled"): cv.boolean,
            vol.Optional("start_time"): cv.time,
        },
        "async_set_sleep_mode",
    )
    platform.async_register_entity_service(
        SERVICE_SET_WAIT_TIME,
        {vol.Required("minutes"): vol.All(vol.Coerce(int), vol.In(VALID_WAIT_TIMES))},
        "async_set_wait_time",
    )


class LitterRobotCleaner(LitterRobotControlEntity, VacuumEntity):
    """Litter-Robot "Vacuum" Cleaner."""

    @property
    def supported_features(self) -> int:
        """Flag cleaner robot features that are supported."""
        return SUPPORT_LITTERROBOT

    @property
    def state(self) -> str:
        """Return the state of the cleaner."""
        switcher = {
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

        return switcher.get(self.robot.status, STATE_ERROR)

    @property
    def status(self) -> str:
        """Return the status of the cleaner."""
        return (
            f"{self.robot.status.text}{' (Sleeping)' if self.robot.is_sleeping else ''}"
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the cleaner on, starting a clean cycle."""
        await self.perform_action_and_refresh(self.robot.set_power_status, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the unit off, stopping any cleaning in progress as is."""
        await self.perform_action_and_refresh(self.robot.set_power_status, False)

    async def async_start(self) -> None:
        """Start a clean cycle."""
        await self.perform_action_and_refresh(self.robot.start_cleaning)

    async def async_reset_waste_drawer(self) -> None:
        """Reset the waste drawer level."""
        await self.robot.reset_waste_drawer()
        self.coordinator.async_set_updated_data(True)

    async def async_set_sleep_mode(
        self, enabled: bool, start_time: str | None = None
    ) -> None:
        """Set the sleep mode."""
        await self.perform_action_and_refresh(
            self.robot.set_sleep_mode,
            enabled,
            self.parse_time_at_default_timezone(start_time),
        )

    async def async_set_wait_time(self, minutes: int) -> None:
        """Set the wait time."""
        await self.perform_action_and_refresh(self.robot.set_wait_time, minutes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            "clean_cycle_wait_time_minutes": self.robot.clean_cycle_wait_time_minutes,
            "is_sleeping": self.robot.is_sleeping,
            "sleep_mode_enabled": self.robot.sleep_mode_enabled,
            "power_status": self.robot.power_status,
            "status_code": self.robot.status_code,
            "last_seen": self.robot.last_seen,
        }
