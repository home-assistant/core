"""Support for Litter-Robot switches."""
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .hub import LitterRobotEntity


class LitterRobotNightLightModeSwitch(LitterRobotEntity, SwitchEntity):
    """Litter-Robot Night Light Mode Switch."""

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


class LitterRobotPanelLockoutSwitch(LitterRobotEntity, SwitchEntity):
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


ROBOT_SWITCHES = {
    "Night Light Mode": LitterRobotNightLightModeSwitch,
    "Panel Lockout": LitterRobotPanelLockoutSwitch,
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
