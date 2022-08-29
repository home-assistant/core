"""Support for Litter-Robot switches."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pylitterbot import FeederRobot, LitterRobot, Robot

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotConfigEntity
from .hub import LitterRobotHub


@dataclass
class RobotSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes robot switch entities."""

    icons: tuple[str | None, str | None] = (None, None)
    set_fn: Callable[
        [LitterRobot | FeederRobot], Callable[[bool], Coroutine[Any, Any, bool]]
    ] | None = None


ROBOT_SWITCHES = [
    RobotSwitchEntityDescription(
        key="night_light_mode_enabled",
        name="Night Light Mode",
        icons=("mdi:lightbulb-on", "mdi:lightbulb-off"),
        set_fn=lambda robot: robot.set_night_light,
    ),
    RobotSwitchEntityDescription(
        key="panel_lock_enabled",
        name="Panel Lockout",
        icons=("mdi:lock", "mdi:lock-open"),
        set_fn=lambda robot: robot.set_panel_lockout,
    ),
]


class RobotSwitchEntity(LitterRobotConfigEntity, SwitchEntity):
    """Litter-Robot switch entity."""

    entity_description: RobotSwitchEntityDescription

    def __init__(
        self,
        robot: Robot,
        hub: LitterRobotHub,
        description: RobotSwitchEntityDescription,
    ) -> None:
        """Initialize a Litter-Robot switch entity."""
        assert description.name
        super().__init__(robot, description.name, hub)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        if self._refresh_callback is not None:
            return self._assumed_state
        return bool(getattr(self.robot, self.entity_description.key))

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        icon_on, icon_off = self.entity_description.icons
        return icon_on if self.is_on else icon_off

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if set_fn := self.entity_description.set_fn:
            await self.perform_action_and_assume_state(set_fn(self.robot), True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if set_fn := self.entity_description.set_fn:
            await self.perform_action_and_assume_state(set_fn(self.robot), False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot switches using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RobotSwitchEntity(robot=robot, hub=hub, description=description)
        for description in ROBOT_SWITCHES
        for robot in hub.account.robots
        if isinstance(robot, (LitterRobot, FeederRobot))
    )
