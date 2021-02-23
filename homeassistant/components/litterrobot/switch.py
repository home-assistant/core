"""Support for Litter-Robot switches."""
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .hub import LitterRobotEntity

NIGHT_LIGHT = "Night Light"
PANEL_LOCKOUT = "Panel Lockout"
SLEEP_MODE = "Sleep Mode"

DEFAULT_SLEEP_TIME = "22:00"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Litter-Robot switches using config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for robot in hub.account.robots:
        entities.append(LitterRobotSwitch(robot, NIGHT_LIGHT, hub))
        entities.append(LitterRobotSwitch(robot, PANEL_LOCKOUT, hub))
        entities.append(LitterRobotSwitch(robot, SLEEP_MODE, hub))

    if entities:
        async_add_entities(entities, True)


class LitterRobotSwitch(LitterRobotEntity, ToggleEntity):
    """Litter-Robot Switches."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self.entity_type == NIGHT_LIGHT:
            return self.robot.night_light_active
        if self.entity_type == PANEL_LOCKOUT:
            return self.robot.panel_lock_active
        if self.entity_type == SLEEP_MODE:
            return self.robot.sleep_mode_active

    @property
    def icon(self):
        """Return the icon based on the entity_type."""
        if self.entity_type == NIGHT_LIGHT:
            return "mdi:lightbulb-on" if self.is_on else "mdi:lightbulb-off"
        if self.entity_type == PANEL_LOCKOUT:
            return "mdi:lock" if self.is_on else "mdi:lock-open"
        if self.entity_type == SLEEP_MODE:
            return "mdi:sleep" if self.is_on else "mdi:sleep-off"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.entity_type == NIGHT_LIGHT:
            await self.perform_action_and_refresh(self.robot.set_night_light, True)
        elif self.entity_type == PANEL_LOCKOUT:
            await self.perform_action_and_refresh(self.robot.set_panel_lockout, True)
        elif self.entity_type == SLEEP_MODE:
            await self.perform_action_and_refresh(
                self.robot.set_sleep_mode,
                True,
                self.parse_time_at_default_timezone(DEFAULT_SLEEP_TIME),
            )

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.entity_type == NIGHT_LIGHT:
            await self.perform_action_and_refresh(self.robot.set_night_light, False)
        elif self.entity_type == PANEL_LOCKOUT:
            await self.perform_action_and_refresh(self.robot.set_panel_lockout, False)
        elif self.entity_type == SLEEP_MODE:
            await self.perform_action_and_refresh(self.robot.set_sleep_mode, False)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        if self.entity_type == SLEEP_MODE:
            [start_time, end_time] = [None, None]
            if self.is_on:
                start_time = dt_util.as_local(
                    self.robot.sleep_mode_start_time
                ).strftime("%H:%M:00")
                end_time = dt_util.as_local(self.robot.sleep_mode_end_time).strftime(
                    "%H:%M:00"
                )
            return {
                "start_time": start_time,
                "end_time": end_time,
            }
