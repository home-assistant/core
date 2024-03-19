"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""

from __future__ import annotations

from pyspcwebgw import SpcWebGateway
from pyspcwebgw.area import Area
from pyspcwebgw.const import AreaMode

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_API, SIGNAL_UPDATE_ALARM


def _get_alarm_state(area: Area) -> str | None:
    """Get the alarm state."""

    if area.verified_alarm:
        return STATE_ALARM_TRIGGERED

    mode_to_state = {
        AreaMode.UNSET: STATE_ALARM_DISARMED,
        AreaMode.PART_SET_A: STATE_ALARM_ARMED_HOME,
        AreaMode.PART_SET_B: STATE_ALARM_ARMED_NIGHT,
        AreaMode.FULL_SET: STATE_ALARM_ARMED_AWAY,
    }
    return mode_to_state.get(area.mode)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SPC alarm control panel platform."""
    if discovery_info is None:
        return
    api: SpcWebGateway = hass.data[DATA_API]
    async_add_entities([SpcAlarm(area=area, api=api) for area in api.areas.values()])


class SpcAlarm(alarm.AlarmControlPanelEntity):
    """Representation of the SPC alarm panel."""

    _attr_should_poll = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )

    def __init__(self, area: Area, api: SpcWebGateway) -> None:
        """Initialize the SPC alarm panel."""
        self._area = area
        self._api = api
        self._attr_name = area.name

    async def async_added_to_hass(self) -> None:
        """Call for adding new entities."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_ALARM.format(self._area.id),
                self._update_callback,
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def changed_by(self) -> str:
        """Return the user the last change was triggered by."""
        return self._area.last_changed_by

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return _get_alarm_state(self._area)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""

        await self._api.change_mode(area=self._area, new_mode=AreaMode.UNSET)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""

        await self._api.change_mode(area=self._area, new_mode=AreaMode.PART_SET_A)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm home command."""

        await self._api.change_mode(area=self._area, new_mode=AreaMode.PART_SET_B)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""

        await self._api.change_mode(area=self._area, new_mode=AreaMode.FULL_SET)
