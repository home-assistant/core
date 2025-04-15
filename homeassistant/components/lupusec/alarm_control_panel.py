"""Support for Lupusec System alarm control panels."""

from __future__ import annotations

from datetime import timedelta

import lupupy

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN
from .entity import LupusecDevice

SCAN_INTERVAL = timedelta(seconds=2)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an alarm control panel for a Lupusec device."""
    data = hass.data[DOMAIN][config_entry.entry_id]

    alarm = await hass.async_add_executor_job(data.get_alarm)

    async_add_entities([LupusecAlarm(data, alarm, config_entry.entry_id)])


class LupusecAlarm(LupusecDevice, AlarmControlPanelEntity):
    """An alarm_control_panel implementation for Lupusec."""

    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_code_arm_required = False

    def __init__(
        self, data: lupupy.Lupusec, device: lupupy.devices.LupusecAlarm, entry_id: str
    ) -> None:
        """Initialize the LupusecAlarm class."""
        super().__init__(device)
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device.name,
            manufacturer="Lupus Electronics",
            model=f"Lupusec-XT{data.model}",
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        if self._device.is_standby:
            state = AlarmControlPanelState.DISARMED
        elif self._device.is_away:
            state = AlarmControlPanelState.ARMED_AWAY
        elif self._device.is_home:
            state = AlarmControlPanelState.ARMED_HOME
        elif self._device.is_alarm_triggered:
            state = AlarmControlPanelState.TRIGGERED
        else:
            state = None
        return state

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._device.set_away()

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._device.set_standby()

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._device.set_home()
