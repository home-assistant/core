"""
Support for HomematicIP alarm control panel.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.homematicip_cloud/
"""

import logging

from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED)
from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN as HMIPC_DOMAIN,
    HMIPC_HAPID)


DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

HMIP_ZONE_AWAY = 'EXTERNAL'
HMIP_ZONE_HOME = 'INTERNAL'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the HomematicIP alarm control devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the HomematicIP alarm control panel from a config entry."""
    from homematicip.aio.group import AsyncSecurityZoneGroup

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for group in home.groups:
        if isinstance(group, AsyncSecurityZoneGroup):
            devices.append(HomematicipSecurityZone(home, group))

    if devices:
        async_add_devices(devices)


class HomematicipSecurityZone(HomematicipGenericDevice, AlarmControlPanel):
    """Representation of an HomematicIP security zone group."""

    def __init__(self, home, device):
        """Initialize the security zone group."""
        device.modelType = 'Group-SecurityZone'
        device.windowState = ''
        super().__init__(home, device)

    @property
    def state(self):
        """Return the state of the device."""
        from homematicip.base.enums import WindowState

        if self._device.active:
            if (self._device.sabotage or self._device.motionDetected or
                    self._device.windowState == WindowState.OPEN):
                return STATE_ALARM_TRIGGERED

            active = self._home.get_security_zones_activation()
            if active == (True, True):
                return STATE_ALARM_ARMED_AWAY
            if active == (False, True):
                return STATE_ALARM_ARMED_HOME

        return STATE_ALARM_DISARMED

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self._home.set_security_zones_activation(False, False)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self._home.set_security_zones_activation(True, False)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._home.set_security_zones_activation(True, True)
