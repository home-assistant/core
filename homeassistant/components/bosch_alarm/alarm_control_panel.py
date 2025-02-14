"""Support for Bosch Alarm Panel."""

from __future__ import annotations

from collections.abc import Mapping
import datetime as dt
import logging
from typing import Any

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

READY_STATE_ATTR = "ready_to_arm"
READY_STATE_NO = "no"
READY_STATE_HOME = "home"
READY_STATE_AWAY = "away"
FAULTED_POINTS_ATTR = "faulted_points"
ALARMS_ATTR = "alarms"
DATETIME_ATTR = "datetime"

SET_DATE_TIME_SERVICE_NAME = "set_date_time"
SET_DATE_TIME_SCHEMA = make_entity_service_schema(
    {vol.Optional(DATETIME_ATTR): cv.datetime}
)


class AreaAlarmControlPanel(AlarmControlPanelEntity):
    """An alarm control panel entity for a bosch alarm panel."""

    def __init__(self, panel_conn, arming_code, area_id, area, unique_id) -> None:
        """Initialise a Bosch Alarm control panel entity."""
        self._panel = panel_conn.panel
        self._arming_code = arming_code
        self._area_id = area_id
        self._area = area
        self._attr_unique_id = unique_id
        self._attr_has_entity_name = True
        self._attr_device_info = panel_conn.device_info()
        self._attr_code_arm_required = arming_code is not None
        self._attr_should_poll = False
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
        )

    @property
    def code_format(self) -> alarm.CodeFormat | None:
        """Return the code format for the current arming code."""
        if self._arming_code is None:
            return None
        if self._arming_code.isnumeric():
            return alarm.CodeFormat.NUMBER
        return alarm.CodeFormat.TEXT

    @property
    def name(self) -> str:
        """Return the name of the alarm."""
        return self._area.name

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        if self._area.is_triggered():
            return AlarmControlPanelState.TRIGGERED
        if self._area.is_disarmed():
            return AlarmControlPanelState.DISARMED
        if self._area.is_arming():
            return AlarmControlPanelState.ARMING
        if self._area.is_pending():
            return AlarmControlPanelState.PENDING
        if self._area.is_part_armed():
            return AlarmControlPanelState.ARMED_HOME
        if self._area.is_all_armed():
            return AlarmControlPanelState.ARMED_AWAY
        return None

    def _arming_code_correct(self, code) -> bool:
        """Validate a given code is correct for this panel."""
        return code == self._arming_code

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this panel."""
        if self._arming_code_correct(code):
            await self._panel.area_disarm(self._area_id)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if self._arming_code_correct(code):
            await self._panel.area_arm_part(self._area_id)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if self._arming_code_correct(code):
            await self._panel.area_arm_all(self._area_id)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        ready_state = READY_STATE_NO
        if self._area.all_ready:
            ready_state = READY_STATE_AWAY
        elif self._area.part_ready:
            ready_state = READY_STATE_HOME
        return {
            READY_STATE_ATTR: ready_state,
            FAULTED_POINTS_ATTR: self._area.faults,
            ALARMS_ATTR: "\n".join(self._area.alarms),
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity attached to hass."""
        self._area.status_observer.attach(self.schedule_update_ha_state)
        self._area.alarm_observer.attach(self.schedule_update_ha_state)
        self._area.ready_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity removed from hass."""
        self._area.status_observer.detach(self.schedule_update_ha_state)
        self._area.alarm_observer.detach(self.schedule_update_ha_state)
        self._area.ready_observer.detach(self.schedule_update_ha_state)

    async def set_panel_date(self, **kwargs: Any) -> None:
        """Set the date and time on a bosch alarm panel."""
        value: dt.datetime = kwargs.get(DATETIME_ATTR, dt_util.now())
        await self._panel.set_panel_date(value)


async def async_setup_entry(
    hass: HomeAssistant | None,
    config_entry: ConfigEntry,
    async_add_entities: entity_platform.AddConfigEntryEntitiesCallback,
) -> None:
    """Set up control panels for each area."""
    panel_conn = config_entry.runtime_data
    panel = panel_conn.panel

    arming_code = config_entry.options.get(CONF_CODE, None)

    async_add_entities(
        AreaAlarmControlPanel(
            panel_conn,
            arming_code,
            area_id,
            area,
            f"{panel_conn.unique_id}_area_{area_id}",
        )
        for (area_id, area) in panel.areas.items()
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SET_DATE_TIME_SERVICE_NAME, SET_DATE_TIME_SCHEMA, "set_panel_date"
    )
