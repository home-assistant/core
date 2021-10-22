"""Support for deCONZ alarm control panel devices."""
from __future__ import annotations

from pydeconz.sensor import (
    ANCILLARY_CONTROL_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY,
    ANCILLARY_CONTROL_ARMING_AWAY,
    ANCILLARY_CONTROL_ARMING_NIGHT,
    ANCILLARY_CONTROL_ARMING_STAY,
    ANCILLARY_CONTROL_DISARMED,
    ANCILLARY_CONTROL_ENTRY_DELAY,
    ANCILLARY_CONTROL_EXIT_DELAY,
    ANCILLARY_CONTROL_IN_ALARM,
    AncillaryControl,
)

from homeassistant.components.alarm_control_panel import (
    DOMAIN,
    FORMAT_NUMBER,
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    AlarmControlPanelEntity,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

DECONZ_TO_ALARM_STATE = {
    ANCILLARY_CONTROL_ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY: STATE_ALARM_ARMED_HOME,
    ANCILLARY_CONTROL_ARMING_AWAY: STATE_ALARM_ARMING,
    ANCILLARY_CONTROL_ARMING_NIGHT: STATE_ALARM_ARMING,
    ANCILLARY_CONTROL_ARMING_STAY: STATE_ALARM_ARMING,
    ANCILLARY_CONTROL_DISARMED: STATE_ALARM_DISARMED,
    ANCILLARY_CONTROL_ENTRY_DELAY: STATE_ALARM_PENDING,
    ANCILLARY_CONTROL_EXIT_DELAY: STATE_ALARM_PENDING,
    ANCILLARY_CONTROL_IN_ALARM: STATE_ALARM_TRIGGERED,
}


def get_alarm_system_for_unique_id(gateway, unique_id: str):
    """Retrieve alarm system unique ID is registered to."""
    for alarm_system in gateway.api.alarmsystems.values():
        if unique_id in alarm_system.devices:
            return alarm_system


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up the deCONZ alarm control panel devices.

    Alarm control panels are based on the same device class as sensors in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_alarm_control_panel(sensors=gateway.api.sensors.values()) -> None:
        """Add alarm control panel devices from deCONZ."""
        entities = []

        for sensor in sensors:

            if (
                isinstance(sensor, AncillaryControl)
                and sensor.unique_id not in gateway.entities[DOMAIN]
                and get_alarm_system_for_unique_id(gateway, sensor.unique_id)
            ):

                entities.append(DeconzAlarmControlPanel(sensor, gateway))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.async_signal_new_device(NEW_SENSOR),
            async_add_alarm_control_panel,
        )
    )

    async_add_alarm_control_panel()


class DeconzAlarmControlPanel(DeconzDevice, AlarmControlPanelEntity):
    """Representation of a deCONZ alarm control panel."""

    TYPE = DOMAIN

    _attr_code_format = FORMAT_NUMBER
    _attr_supported_features = (
        SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_NIGHT
    )

    def __init__(self, device, gateway) -> None:
        """Set up alarm control panel device."""
        super().__init__(device, gateway)
        self.alarm_system = get_alarm_system_for_unique_id(gateway, device.unique_id)

    @callback
    def async_update_callback(self, force_update: bool = False) -> None:
        """Update the control panels state."""
        keys = {"panel", "reachable"}
        if force_update or (
            self._device.changed_keys.intersection(keys)
            and self._device.state in DECONZ_TO_ALARM_STATE
        ):
            super().async_update_callback(force_update=force_update)

    @property
    def state(self) -> str | None:
        """Return the state of the control panel."""
        return DECONZ_TO_ALARM_STATE.get(self._device.state)

    async def async_alarm_arm_away(self, code: None = None) -> None:
        """Send arm away command."""
        await self.alarm_system.arm_away(code)

    async def async_alarm_arm_home(self, code: None = None) -> None:
        """Send arm home command."""
        await self.alarm_system.arm_stay(code)

    async def async_alarm_arm_night(self, code: None = None) -> None:
        """Send arm night command."""
        await self.alarm_system.arm_night(code)

    async def async_alarm_disarm(self, code: None = None) -> None:
        """Send disarm command."""
        await self.alarm_system.disarm(code)
