"""Support for deCONZ climate devices."""
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
    ANCILLARY_CONTROL_NOT_READY,
    AncillaryControl,
)

from homeassistant.components.alarm_control_panel import (
    DOMAIN,
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
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

SERVICE_ALARM_ARMING_AWAY = "alarm_arming_away"
SERVICE_ALARM_ARMING_HOME = "alarm_arming_home"
SERVICE_ALARM_ARMING_NIGHT = "alarm_arming_night"
SERVICE_ALARM_ENTRY_DELAY = "alarm_entry_delay"
SERVICE_ALARM_EXIT_DELAY = "alarm_exit_delay"
SERVICE_ALARM_NOT_READY = "alarm_not_ready"
SERVICE_ALARM_TRIGGERED = "alarm_triggered"

DECONZ_TO_ALARM_STATE = {
    ANCILLARY_CONTROL_ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY: STATE_ALARM_ARMED_HOME,
    ANCILLARY_CONTROL_DISARMED: STATE_ALARM_DISARMED,
    ANCILLARY_CONTROL_ARMING_AWAY: STATE_ALARM_ARMING,
    ANCILLARY_CONTROL_ARMING_NIGHT: STATE_ALARM_ARMING,
    ANCILLARY_CONTROL_ARMING_STAY: STATE_ALARM_ARMING,
    ANCILLARY_CONTROL_ENTRY_DELAY: STATE_ALARM_PENDING,
    ANCILLARY_CONTROL_EXIT_DELAY: STATE_ALARM_PENDING,
    ANCILLARY_CONTROL_IN_ALARM: STATE_ALARM_TRIGGERED,
    ANCILLARY_CONTROL_NOT_READY: STATE_ALARM_PENDING,  # ???
}


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
                sensor.type in AncillaryControl.ZHATYPE
                and sensor.uniqueid not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzAlarmControlPanel(sensor, gateway))

        if entities:
            async_add_entities(entities)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass,
            gateway.async_signal_new_device(NEW_SENSOR),
            async_add_alarm_control_panel,
        )
    )

    async_add_alarm_control_panel()

    # Custom services

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_ALARM_ARMING_AWAY, {}, "async_alarm_arming_away"
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_ARMING_HOME, {}, "async_alarm_arming_home"
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_ARMING_NIGHT, {}, "async_alarm_arming_night"
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_ENTRY_DELAY, {}, "async_alarm_entry_delay"
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_EXIT_DELAY, {}, "async_alarm_exit_delay"
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_NOT_READY, {}, "async_alarm_not_ready"
    )

    platform.async_register_entity_service(
        SERVICE_ALARM_TRIGGERED, {}, "async_alarm_triggered"
    )


class DeconzAlarmControlPanel(DeconzDevice, AlarmControlPanelEntity):
    """Representation of a deCONZ alarm control panel."""

    TYPE = DOMAIN

    def __init__(self, device, gateway) -> None:
        """Set up alarm control panel device."""
        super().__init__(device, gateway)

        self._features = SUPPORT_ALARM_ARM_AWAY
        self._features |= SUPPORT_ALARM_ARM_HOME
        self._features |= SUPPORT_ALARM_ARM_NIGHT

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._features

    @property
    def code_arm_required(self) -> bool:
        """Code is not required for arm actions."""
        return False

    @property
    def code_format(self) -> None:
        """Code is not supported."""
        return None

    @callback
    def async_update_callback(self, force_update: bool = False) -> None:
        """Update the control panels state."""
        keys = {"panel", "reachable"}
        if force_update or self._device.changed_keys.intersection(keys):
            super().async_update_callback(force_update=force_update)

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return DECONZ_TO_ALARM_STATE.get(self._device.panel)

    async def async_alarm_arm_away(self, code: None = None) -> None:
        """Send arm away command."""
        await self._device.arm_away()

    async def async_alarm_arm_home(self, code: None = None) -> None:
        """Send arm home command."""
        await self._device.arm_stay()

    async def async_alarm_arm_night(self, code: None = None) -> None:
        """Send arm night command."""
        await self._device.arm_night()

    async def async_alarm_disarm(self, code: None = None) -> None:
        """Send disarm command."""
        await self._device.disarm()

    # Custom services

    async def async_alarm_arming_away(self) -> None:
        """Send arming away command."""
        await self._device.arming_away()

    async def async_alarm_arming_home(self) -> None:
        """Send arming home command."""
        await self._device.arming_stay()

    async def async_alarm_arming_night(self) -> None:
        """Send arming night command."""
        await self._device.arming_night()

    async def async_alarm_entry_delay(self) -> None:
        """Send entry delay command."""
        await self._device.entry_delay()

    async def async_alarm_exit_delay(self) -> None:
        """Send exit delay command."""
        await self._device.exit_delay()

    async def async_alarm_not_ready(self) -> None:
        """Send not ready command."""
        await self._device.not_ready()

    async def async_alarm_triggered(self) -> None:
        """Send in alarm command."""
        await self._device.in_alarm()
