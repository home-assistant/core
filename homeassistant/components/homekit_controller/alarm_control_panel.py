"""Support for Homekit Alarm Control Panel."""

from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import HomeKitEntity

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit alarm control panel."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if service.type != ServicesTypes.SECURITY_SYSTEM:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        entity = HomeKitAlarmControlPanelEntity(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.ALARM_CONTROL_PANEL
        )
        async_add_entities([entity])
        return True

    conn.add_listener(async_add_service)


class HomeKitAlarmControlPanelEntity(HomeKitEntity, AlarmControlPanelEntity):
    """Representation of a Homekit Alarm Control Panel."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT,
            CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET,
            CharacteristicsTypes.BATTERY_LEVEL,
        ]

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return CURRENT_STATE_MAP[
            self.service.value(CharacteristicsTypes.SECURITY_SYSTEM_STATE_CURRENT)
        ]

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self.set_alarm_state(STATE_ALARM_DISARMED, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_AWAY, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send stay command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_HOME, code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send night command."""
        await self.set_alarm_state(STATE_ALARM_ARMED_NIGHT, code)

    async def set_alarm_state(self, state: str, code: str | None = None) -> None:
        """Send state command."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.SECURITY_SYSTEM_STATE_TARGET: TARGET_STATE_MAP[state]}
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the optional state attributes."""
        battery_level = self.service.value(CharacteristicsTypes.BATTERY_LEVEL)

        if not battery_level:
            return {}
        return {ATTR_BATTERY_LEVEL: battery_level}
