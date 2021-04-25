"""Support for deCONZ alarm control panel devices."""
from __future__ import annotations

from pydeconz.sensor import (
    ANCILLARY_CONTROL_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY,
    ANCILLARY_CONTROL_DISARMED,
    AncillaryControl,
)
import voluptuous as vol

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
    STATE_ALARM_DISARMED,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_SENSOR
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

PANEL_ARMING_AWAY = "arming_away"
PANEL_ARMING_HOME = "arming_home"
PANEL_ARMING_NIGHT = "arming_night"
PANEL_ENTRY_DELAY = "entry_delay"
PANEL_EXIT_DELAY = "exit_delay"
PANEL_NOT_READY_TO_ARM = "not_ready_to_arm"

SERVICE_ALARM_PANEL_STATE = "alarm_panel_state"
CONF_ALARM_PANEL_STATE = "panel_state"
SERVICE_ALARM_PANEL_STATE_SCHEMA = {
    vol.Required(CONF_ALARM_PANEL_STATE): vol.In(
        [
            PANEL_ARMING_AWAY,
            PANEL_ARMING_HOME,
            PANEL_ARMING_NIGHT,
            PANEL_ENTRY_DELAY,
            PANEL_EXIT_DELAY,
            PANEL_NOT_READY_TO_ARM,
        ]
    )
}

DECONZ_TO_ALARM_STATE = {
    ANCILLARY_CONTROL_ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY: STATE_ALARM_ARMED_HOME,
    ANCILLARY_CONTROL_DISARMED: STATE_ALARM_DISARMED,
}


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up the deCONZ alarm control panel devices.

    Alarm control panels are based on the same device class as sensors in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    platform = entity_platform.current_platform.get()

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
            platform.async_register_entity_service(
                SERVICE_ALARM_PANEL_STATE,
                SERVICE_ALARM_PANEL_STATE_SCHEMA,
                "async_set_panel_state",
            )
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

    def __init__(self, device, gateway) -> None:
        """Set up alarm control panel device."""
        super().__init__(device, gateway)

        self._features = SUPPORT_ALARM_ARM_AWAY
        self._features |= SUPPORT_ALARM_ARM_HOME
        self._features |= SUPPORT_ALARM_ARM_NIGHT

        self._service_to_device_panel_command = {
            PANEL_ARMING_AWAY: self._device.arming_away,
            PANEL_ARMING_HOME: self._device.arming_stay,
            PANEL_ARMING_NIGHT: self._device.arming_night,
            PANEL_ENTRY_DELAY: self._device.entry_delay,
            PANEL_EXIT_DELAY: self._device.exit_delay,
            PANEL_NOT_READY_TO_ARM: self._device.not_ready_to_arm,
        }

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
        keys = {"armed", "reachable"}
        if force_update or (
            self._device.changed_keys.intersection(keys)
            and self._device.state in DECONZ_TO_ALARM_STATE
        ):
            super().async_update_callback(force_update=force_update)

    @property
    def state(self) -> str:
        """Return the state of the control panel."""
        return DECONZ_TO_ALARM_STATE.get(self._device.state, None)

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

    async def async_set_panel_state(self, panel_state: str) -> None:
        """Send panel_state command."""
        await self._service_to_device_panel_command[panel_state]()
