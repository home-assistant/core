"""Support for deCONZ alarm control panel devices."""
from __future__ import annotations

from pydeconz.models.alarm_system import AlarmSystemArmAction
from pydeconz.models.event import EventType
from pydeconz.models.sensor.ancillary_control import (
    AncillaryControl,
    AncillaryControlPanel,
)

from homeassistant.components.alarm_control_panel import (
    DOMAIN,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

DECONZ_TO_ALARM_STATE = {
    AncillaryControlPanel.ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    AncillaryControlPanel.ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
    AncillaryControlPanel.ARMED_STAY: STATE_ALARM_ARMED_HOME,
    AncillaryControlPanel.ARMING_AWAY: STATE_ALARM_ARMING,
    AncillaryControlPanel.ARMING_NIGHT: STATE_ALARM_ARMING,
    AncillaryControlPanel.ARMING_STAY: STATE_ALARM_ARMING,
    AncillaryControlPanel.DISARMED: STATE_ALARM_DISARMED,
    AncillaryControlPanel.ENTRY_DELAY: STATE_ALARM_PENDING,
    AncillaryControlPanel.EXIT_DELAY: STATE_ALARM_PENDING,
    AncillaryControlPanel.IN_ALARM: STATE_ALARM_TRIGGERED,
}


def get_alarm_system_id_for_unique_id(
    gateway: DeconzGateway, unique_id: str
) -> str | None:
    """Retrieve alarm system ID the unique ID is registered to."""
    for alarm_system in gateway.api.alarmsystems.values():
        if unique_id in alarm_system.devices:
            return alarm_system.resource_id
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ alarm control panel devices."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add alarm control panel devices from deCONZ."""
        sensor = gateway.api.sensors.ancillary_control[sensor_id]
        if alarm_system_id := get_alarm_system_id_for_unique_id(
            gateway, sensor.unique_id
        ):
            async_add_entities(
                [DeconzAlarmControlPanel(sensor, gateway, alarm_system_id)]
            )

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors.ancillary_control,
    )


class DeconzAlarmControlPanel(DeconzDevice, AlarmControlPanelEntity):
    """Representation of a deCONZ alarm control panel."""

    TYPE = DOMAIN
    _device: AncillaryControl

    _attr_code_format = CodeFormat.NUMBER
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(
        self,
        device: AncillaryControl,
        gateway: DeconzGateway,
        alarm_system_id: str,
    ) -> None:
        """Set up alarm control panel device."""
        super().__init__(device, gateway)
        self.alarm_system_id = alarm_system_id

    @callback
    def async_update_callback(self) -> None:
        """Update the control panels state."""
        keys = {"panel", "reachable"}
        if (
            self._device.changed_keys.intersection(keys)
            and self._device.panel in DECONZ_TO_ALARM_STATE
        ):
            super().async_update_callback()

    @property
    def state(self) -> str | None:
        """Return the state of the control panel."""
        if self._device.panel in DECONZ_TO_ALARM_STATE:
            return DECONZ_TO_ALARM_STATE[self._device.panel]
        return None

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if code:
            await self.gateway.api.alarmsystems.arm(
                self.alarm_system_id, AlarmSystemArmAction.AWAY, code
            )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if code:
            await self.gateway.api.alarmsystems.arm(
                self.alarm_system_id, AlarmSystemArmAction.STAY, code
            )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        if code:
            await self.gateway.api.alarmsystems.arm(
                self.alarm_system_id, AlarmSystemArmAction.NIGHT, code
            )

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code:
            await self.gateway.api.alarmsystems.arm(
                self.alarm_system_id, AlarmSystemArmAction.DISARM, code
            )
