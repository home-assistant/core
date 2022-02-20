"""Support for Litter-Robot selects."""
from __future__ import annotations

from pylitterbot.robot import VALID_WAIT_TIMES

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotConfigEntity
from .hub import LitterRobotHub

TYPE_CLEAN_CYCLE_WAIT_TIME_MINUTES = "Clean Cycle Wait Time Minutes"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot selects using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [
            LitterRobotSelect(
                robot=robot, entity_type=TYPE_CLEAN_CYCLE_WAIT_TIME_MINUTES, hub=hub
            )
            for robot in hub.account.robots
        ]
    )


class LitterRobotSelect(LitterRobotConfigEntity, SelectEntity):
    """Litter-Robot Select."""

    _attr_icon = "mdi:timer-outline"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return str(self.robot.clean_cycle_wait_time_minutes)

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return [str(minute) for minute in VALID_WAIT_TIMES]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.perform_action_and_refresh(self.robot.set_wait_time, int(option))
