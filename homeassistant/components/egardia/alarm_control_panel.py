"""Interfaces with Egardia/Woonveilig alarm control panel."""

from __future__ import annotations

import logging

import requests

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_REPORT_SERVER_CODES,
    CONF_REPORT_SERVER_ENABLED,
    CONF_REPORT_SERVER_PORT,
    EGARDIA_DEVICE,
    EGARDIA_SERVER,
    REPORT_SERVER_CODES_IGNORE,
)

_LOGGER = logging.getLogger(__name__)

STATES = {
    "ARM": STATE_ALARM_ARMED_AWAY,
    "DAY HOME": STATE_ALARM_ARMED_HOME,
    "DISARM": STATE_ALARM_DISARMED,
    "ARMHOME": STATE_ALARM_ARMED_HOME,
    "HOME": STATE_ALARM_ARMED_HOME,
    "NIGHT HOME": STATE_ALARM_ARMED_NIGHT,
    "TRIGGERED": STATE_ALARM_TRIGGERED,
}


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Egardia Alarm Control Panael platform."""
    if discovery_info is None:
        return
    device = EgardiaAlarm(
        discovery_info["name"],
        hass.data[EGARDIA_DEVICE],
        discovery_info[CONF_REPORT_SERVER_ENABLED],
        discovery_info.get(CONF_REPORT_SERVER_CODES),
        discovery_info[CONF_REPORT_SERVER_PORT],
    )

    add_entities([device], True)


class EgardiaAlarm(AlarmControlPanelEntity):
    """Representation of a Egardia alarm."""

    _attr_state: str | None
    _attr_code_arm_required = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(
        self, name, egardiasystem, rs_enabled=False, rs_codes=None, rs_port=52010
    ):
        """Initialize the Egardia alarm."""
        self._attr_name = name
        self._egardiasystem = egardiasystem
        self._rs_enabled = rs_enabled
        self._rs_codes = rs_codes
        self._rs_port = rs_port

    async def async_added_to_hass(self) -> None:
        """Add Egardiaserver callback if enabled."""
        if self._rs_enabled:
            _LOGGER.debug("Registering callback to Egardiaserver")
            self.hass.data[EGARDIA_SERVER].register_callback(self.handle_status_event)

    @property
    def should_poll(self) -> bool:
        """Poll if no report server is enabled."""
        if not self._rs_enabled:
            return True
        return False

    def handle_status_event(self, event):
        """Handle the Egardia system status event."""
        if (statuscode := event.get("status")) is not None:
            status = self.lookupstatusfromcode(statuscode)
            self.parsestatus(status)
            self.schedule_update_ha_state()

    def lookupstatusfromcode(self, statuscode):
        """Look at the rs_codes and returns the status from the code."""
        return next(
            (
                status_group.upper()
                for status_group, codes in self._rs_codes.items()
                for code in codes
                if statuscode == code
            ),
            "UNKNOWN",
        )

    def parsestatus(self, status):
        """Parse the status."""
        _LOGGER.debug("Parsing status %s", status)
        # Ignore the statuscode if it is IGNORE
        if status.lower().strip() != REPORT_SERVER_CODES_IGNORE:
            _LOGGER.debug("Not ignoring status %s", status)
            newstatus = STATES.get(status.upper())
            _LOGGER.debug("newstatus %s", newstatus)
            self._attr_state = newstatus
        else:
            _LOGGER.error("Ignoring status")

    def update(self) -> None:
        """Update the alarm status."""
        status = self._egardiasystem.getstate()
        self.parsestatus(status)

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            self._egardiasystem.alarm_disarm()
        except requests.exceptions.RequestException as err:
            _LOGGER.error(
                "Egardia device exception occurred when sending disarm command: %s",
                err,
            )

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        try:
            self._egardiasystem.alarm_arm_home()
        except requests.exceptions.RequestException as err:
            _LOGGER.error(
                "Egardia device exception occurred when sending arm home command: %s",
                err,
            )

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        try:
            self._egardiasystem.alarm_arm_away()
        except requests.exceptions.RequestException as err:
            _LOGGER.error(
                "Egardia device exception occurred when sending arm away command: %s",
                err,
            )
