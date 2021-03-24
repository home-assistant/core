"""Support for Litter-Robot "Vacuum"."""
from __future__ import annotations

from typing import Any, Callable

from pylitterbot.enums import LitterBoxStatus

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_PAUSED,
    SUPPORT_SEND_COMMAND,
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
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .entity import LitterRobotControlEntity
from .hub import LitterRobotHub

SUPPORT_LITTERROBOT = (
    SUPPORT_SEND_COMMAND
    | SUPPORT_START
    | SUPPORT_STATE
    | SUPPORT_STATUS
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)
TYPE_LITTER_BOX = "Litter Box"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for robot in hub.account.robots:
        entities.append(
            LitterRobotCleaner(robot=robot, entity_type=TYPE_LITTER_BOX, hub=hub)
        )

    if entities:
        async_add_entities(entities, True)


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

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the cleaner on, starting a clean cycle."""
        await self.perform_action_and_refresh(self.robot.set_power_status, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the unit off, stopping any cleaning in progress as is."""
        await self.perform_action_and_refresh(self.robot.set_power_status, False)

    async def async_start(self) -> None:
        """Start a clean cycle."""
        await self.perform_action_and_refresh(self.robot.start_cleaning)

    async def async_send_command(
        self, command: str, params: dict[str, Any] | None = None, **kwargs
    ) -> None:
        """Send command.

        Available commands:
          - reset_waste_drawer
            * params: none
          - set_sleep_mode
            * params:
              - enabled: bool
              - sleep_time: str (optional)
          - set_wait_time
            * params:
              - wait_time: int (one of [3,7,15])

        """
        if command == "reset_waste_drawer":
            # Normally we need to request a refresh of data after a command is sent.
            # However, the API for resetting the waste drawer returns a refreshed
            # data set for the robot. Thus, we only need to tell hass to update the
            # state of devices associated with this robot.
            await self.robot.reset_waste_drawer()
            self.coordinator.async_set_updated_data(True)
        elif command == "set_sleep_mode":
            await self.perform_action_and_refresh(
                self.robot.set_sleep_mode,
                params.get("enabled"),
                self.parse_time_at_default_timezone(params.get("sleep_time")),
            )
        elif command == "set_wait_time":
            await self.perform_action_and_refresh(
                self.robot.set_wait_time, params.get("wait_time")
            )
        else:
            raise NotImplementedError()

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
