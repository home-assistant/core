"""Support for deCONZ alarm control panel devices."""
from __future__ import annotations

from pydeconz.models.alarm_system import AlarmSystem
from pydeconz.models.event import EventType
from pydeconz.models.sensor.ancillary_control import (
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


def get_alarm_system_for_unique_id(
    gateway: DeconzGateway, unique_id: str
) -> AlarmSystem | None:
    """Retrieve alarm system unique ID is registered to."""
    for alarm_system in gateway.api.alarmsystems.values():
        if unique_id in alarm_system.devices:
            return alarm_system
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
        if alarm_system := get_alarm_system_for_unique_id(gateway, sensor.unique_id):
            async_add_entities([DeconzAlarmControlPanel(sensor, gateway, alarm_system)])

    config_entry.async_on_unload(
        gateway.api.sensors.ancillary_control.subscribe(
            async_add_sensor,
            EventType.ADDED,
        )
    )

    for sensor_id in gateway.api.sensors.ancillary_control:
        async_add_sensor(EventType.ADDED, sensor_id)


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
        alarm_system: AlarmSystem,
    ) -> None:
        """Set up alarm control panel device."""
        super().__init__(device, gateway)
        self.alarm_system = alarm_system

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
            await self.alarm_system.arm_away(code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if code:
            await self.alarm_system.arm_stay(code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        if code:
            await self.alarm_system.arm_night(code)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if code:
            await self.alarm_system.disarm(code)
