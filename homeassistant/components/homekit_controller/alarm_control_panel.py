"""Support for Homekit Alarm Control Panel."""
import logging

from aiohomekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

ICON = "mdi:security"

_LOGGER = logging.getLogger(__name__)

CURRENT_STATE_MAP = {
    0: STATE_ALARM_ARMED_HOME,
    1: STATE_ALARM_ARMED_AWAY,
    2: STATE_ALARM_ARMED_NIGHT,
    3: STATE_ALARM_DISARMED,
    4: STATE_ALARM_TRIGGERED,
}

TARGET_STATE_MAP = {
    STATE_ALARM_ARMED_HOME: 0,
    STATE_ALARM_ARMED_AWAY: 1,
    STATE_ALARM_ARMED_NIGHT: 2,
    STATE_ALARM_DISARMED: 3,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit alarm control panel."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        if service["stype"] != "security-system":
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([HomeKitAlarmControlPanelEntity(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitAlarmControlPanelEntity(HomeKitEntity, AlarmControlPanelEntity):
    """Representation of a Homekit Alarm Control Panel."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT,
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET,
            CharacteristicsTypes.BATTERY_LEVEL,
        ]

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return CURRENT_STATE_MAP[
            self.service.value(CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT)
        ]

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self.set_alarm_state(STATE_ALARM_DISARMED, code)

    async def async_alarm_arm_away(self, code=None):
        """Send arm command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_AWAY, code)

    async def async_alarm_arm_home(self, code=None):
        """Send stay command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_HOME, code)

    async def async_alarm_arm_night(self, code=None):
        """Send night command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_NIGHT, code)

    async def set_alarm_state(self, state, code=None):
        """Send state command."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET: TARGET_STATE_MAP[state]}
        )

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        attributes = {}

        battery_level = self.service.value(CharacteristicsTypes.BATTERY_LEVEL)
        if battery_level:
            attributes[ATTR_BATTERY_LEVEL] = battery_level

        return attributes
