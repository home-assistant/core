"""Support for Litter-Robot switches."""
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .hub import LitterRobotEntity


class LitterRobotNightLightSwitch(LitterRobotEntity, ToggleEntity):
    """Litter-Robot Night Light Switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.robot.night_light_active

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:lightbulb-on" if self.is_on else "mdi:lightbulb-off"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.perform_action_and_refresh(self.robot.set_night_light, True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.perform_action_and_refresh(self.robot.set_night_light, False)


class LitterRobotPanelLockoutSwitch(LitterRobotEntity, ToggleEntity):
    """Litter-Robot Panel Lockout Switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.robot.panel_lock_active

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:lock" if self.is_on else "mdi:lock-open"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.perform_action_and_refresh(self.robot.set_panel_lockout, True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.perform_action_and_refresh(self.robot.set_panel_lockout, False)


class LitterRobotSleepModeSwitch(LitterRobotEntity, ToggleEntity):
    """Litter-Robot Sleep Mode Switch."""

    DEFAULT_SLEEP_TIME = "22:00"

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.robot.sleep_mode_active

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:sleep" if self.is_on else "mdi:sleep-off"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.perform_action_and_refresh(
            self.robot.set_sleep_mode,
            True,
            self.parse_time_at_default_timezone(self.DEFAULT_SLEEP_TIME),
        )

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.perform_action_and_refresh(self.robot.set_sleep_mode, False)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        [start_time, end_time] = [None, None]
        if self.is_on:
            start_time = dt_util.as_local(self.robot.sleep_mode_start_time).strftime(
                "%H:%M:00"
            )
            end_time = dt_util.as_local(self.robot.sleep_mode_end_time).strftime(
                "%H:%M:00"
            )
        return {
            "start_time": start_time,
            "end_time": end_time,
        }


ROBOT_SWITCHES = {
    "Night Light": LitterRobotNightLightSwitch,
    "Panel Lockout": LitterRobotPanelLockoutSwitch,
    "Sleep Mode": LitterRobotSleepModeSwitch,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Litter-Robot switches using config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for robot in hub.account.robots:
        for switch_type, switch_class in ROBOT_SWITCHES.items():
            entities.append(switch_class(robot, switch_type, hub))

    if entities:
        async_add_entities(entities, True)
