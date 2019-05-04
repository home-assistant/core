"""Support for HomematicIP Cloud alarm control panel."""
import logging

from homematicip.aio.group import AsyncSecurityZoneGroup
from homematicip.aio.home import AsyncHome
from homematicip.base.enums import WindowState

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED)
from homeassistant.core import HomeAssistant

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice

_LOGGER = logging.getLogger(__name__)

CONST_ALARM_CONTROL_PANEL_NAME = 'HmIP Alarm Control Panel'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud alarm control devices."""
    pass


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up the HomematicIP alrm control panel from a config entry."""
    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    security_zones = []
    for group in home.groups:
        if isinstance(group, AsyncSecurityZoneGroup):
            security_zones.append(group)
            # To be removed in a later release.
            devices.append(HomematicipSecurityZone(home, group))
            _LOGGER.warning("Homematic IP: alarm_control_panel.%s is "
                            "deprecated. Please switch to "
                            "alarm_control_panel.*hmip_alarm_control_panel.",
                            group.label)
    if security_zones:
        devices.append(HomematicipAlarmControlPanel(home, security_zones))

    if devices:
        async_add_entities(devices)


class HomematicipSecurityZone(HomematicipGenericDevice, AlarmControlPanel):
    """Representation of an HomematicIP Cloud security zone group."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize the security zone group."""
        device.modelType = 'Group-SecurityZone'
        device.windowState = None
        super().__init__(home, device)

    @property
    def state(self) -> str:
        """Return the state of the device."""
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


class HomematicipAlarmControlPanel(AlarmControlPanel):
    """Representation of an alarm control panel."""

    def __init__(self, home: AsyncHome, security_zones) -> None:
        """Initialize the alarm control panel."""
        self._home = home
        self.alarm_state = STATE_ALARM_DISARMED

        for security_zone in security_zones:
            if security_zone.label == 'INTERNAL':
                self._internal_alarm_zone = security_zone
            else:
                self._external_alarm_zone = security_zone

    @property
    def state(self) -> str:
        """Return the state of the device."""
        activation_state = self._home.get_security_zones_activation()
        # check arm_away
        if activation_state == (True, True):
            if self._internal_alarm_zone_state or \
                    self._external_alarm_zone_state:
                return STATE_ALARM_TRIGGERED
            return STATE_ALARM_ARMED_AWAY
        # check arm_home
        if activation_state == (False, True):
            if self._external_alarm_zone_state:
                return STATE_ALARM_TRIGGERED
            return STATE_ALARM_ARMED_HOME

        return STATE_ALARM_DISARMED

    @property
    def _internal_alarm_zone_state(self) -> bool:
        return _get_zone_alarm_state(self._internal_alarm_zone)

    @property
    def _external_alarm_zone_state(self) -> bool:
        """Return the state of the device."""
        return _get_zone_alarm_state(self._external_alarm_zone)

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self._home.set_security_zones_activation(False, False)

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self._home.set_security_zones_activation(False, True)

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._home.set_security_zones_activation(True, True)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._internal_alarm_zone.on_update(self._async_device_changed)
        self._external_alarm_zone.on_update(self._async_device_changed)

    def _async_device_changed(self, *args, **kwargs):
        """Handle device state changes."""
        _LOGGER.debug("Event %s (%s)", self.name,
                      CONST_ALARM_CONTROL_PANEL_NAME)
        self.async_schedule_update_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the generic device."""
        name = CONST_ALARM_CONTROL_PANEL_NAME
        if self._home.name:
            name = "{} {}".format(self._home.name, name)
        return name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def available(self) -> bool:
        """Device available."""
        return not self._internal_alarm_zone.unreach or \
            not self._external_alarm_zone.unreach

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}_{}".format(self.__class__.__name__, self._home.id)


def _get_zone_alarm_state(security_zone) -> bool:
    if security_zone.active:
        if (security_zone.sabotage or
                security_zone.motionDetected or
                security_zone.presenceDetected or
                security_zone.windowState == WindowState.OPEN or
                security_zone.windowState == WindowState.TILTED):
            return True

    return False
