"""Support for HomematicIP Cloud alarm control panel."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED)

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematicip_cloud']

HMIP_ZONE_AWAY = 'EXTERNAL'
HMIP_ZONE_HOME = 'INTERNAL'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud alarm control devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HomematicIP alarm control panel from a config entry."""
    from homematicip.aio.group import AsyncSecurityZoneGroup

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for group in home.groups:
        if isinstance(group, AsyncSecurityZoneGroup):
            devices.append(HomematicipSecurityZone(home, group))

    if devices:
        async_add_entities(devices)


class HomematicipSecurityZone(HomematicipGenericDevice, AlarmControlPanel):
    """Representation of an HomematicIP Cloud security zone group."""

    def __init__(self, home, device):
        """Initialize the security zone group."""
        device.modelType = 'Group-SecurityZone'
        device.windowState = None
        super().__init__(home, device)

    @property
    def state(self):
        """Return the state of the device."""
        from homematicip.base.enums import WindowState

        if self._device.active:
            if (self._device.sabotage or self._device.motionDetected or
                    self._device.windowState == WindowState.OPEN or
                    self._device.windowState == WindowState.TILTED):
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
        await self._home.set_security_zones_activation(False, True)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._home.set_security_zones_activation(True, True)
