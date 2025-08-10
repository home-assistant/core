"""Support for deCONZ alarm control panel devices."""

from __future__ import annotations

from pydeconz.models.alarm_system import AlarmSystemArmAction
from pydeconz.models.event import EventType
from pydeconz.models.sensor.ancillary_control import (
    AncillaryControl,
    AncillaryControlPanel,
)

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROl_PANEL_DOMAIN,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DeconzConfigEntry
from .entity import DeconzDevice
from .hub import DeconzHub

DECONZ_TO_ALARM_STATE = {
    AncillaryControlPanel.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    AncillaryControlPanel.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    AncillaryControlPanel.ARMED_STAY: AlarmControlPanelState.ARMED_HOME,
    AncillaryControlPanel.ARMING_AWAY: AlarmControlPanelState.ARMING,
    AncillaryControlPanel.ARMING_NIGHT: AlarmControlPanelState.ARMING,
    AncillaryControlPanel.ARMING_STAY: AlarmControlPanelState.ARMING,
    AncillaryControlPanel.DISARMED: AlarmControlPanelState.DISARMED,
    AncillaryControlPanel.ENTRY_DELAY: AlarmControlPanelState.PENDING,
    AncillaryControlPanel.EXIT_DELAY: AlarmControlPanelState.PENDING,
    AncillaryControlPanel.IN_ALARM: AlarmControlPanelState.TRIGGERED,
}


def get_alarm_system_id_for_unique_id(hub: DeconzHub, unique_id: str) -> str | None:
    """Retrieve alarm system ID the unique ID is registered to."""
    for alarm_system in hub.api.alarm_systems.values():
        if unique_id in alarm_system.devices:
            return alarm_system.resource_id
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DeconzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the deCONZ alarm control panel devices."""
    hub = config_entry.runtime_data
    hub.entities[ALARM_CONTROl_PANEL_DOMAIN] = set()

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add alarm control panel devices from deCONZ."""
        sensor = hub.api.sensors.ancillary_control[sensor_id]
        if alarm_system_id := get_alarm_system_id_for_unique_id(hub, sensor.unique_id):
            async_add_entities([DeconzAlarmControlPanel(sensor, hub, alarm_system_id)])

    hub.register_platform_add_device_callback(
        async_add_sensor,
        hub.api.sensors.ancillary_control,
    )


class DeconzAlarmControlPanel(DeconzDevice[AncillaryControl], AlarmControlPanelEntity):
    """Representation of a deCONZ alarm control panel."""

    _update_key = "panel"
    TYPE = ALARM_CONTROl_PANEL_DOMAIN

    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(
        self,
        device: AncillaryControl,
        hub: DeconzHub,
        alarm_system_id: str,
    ) -> None:
        """Set up alarm control panel device."""
        super().__init__(device, hub)
        self.alarm_system_id = alarm_system_id

    @callback
    def async_update_callback(self) -> None:
        """Update the control panels state."""
        if self._device.panel in DECONZ_TO_ALARM_STATE:
            super().async_update_callback()

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the control panel."""
        if self._device.panel in DECONZ_TO_ALARM_STATE:
            return DECONZ_TO_ALARM_STATE[self._device.panel]
        return None

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if code:
            await self.hub.api.alarm_systems.arm(
                self.alarm_system_id, AlarmSystemArmAction.AWAY, code
            )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if code:
            await self.hub.api.alarm_systems.arm(
                self.alarm_system_id, AlarmSystemArmAction.STAY, code
            )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        if code:
            await self.hub.api.alarm_systems.arm(
                self.alarm_system_id, AlarmSystemArmAction.NIGHT, code
            )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code:
            await self.hub.api.alarm_systems.arm(
                self.alarm_system_id, AlarmSystemArmAction.DISARM, code
            )
