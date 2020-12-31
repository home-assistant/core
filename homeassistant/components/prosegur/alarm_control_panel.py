"""Support for Prosegur alarm control panels."""
import logging

from pyprosegur.auth import Auth
from pyprosegur.installation import Installation, Status

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_DISARMED,
    SUPPORT_ALARM_ARM_AWAY,
)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Prosegur alarm control panel platform."""
    async_add_entities(
        [ProsegurAlarm(entry.contractId, hass.data[DOMAIN][entry.entry_id])]
    )


class ProsegurAlarm(alarm.AlarmControlPanelEntity):
    """Representation of a Prosegur alarm status."""

    def __init__(self, contractId: str, auth: Auth):
        """Initialize the Prosegur alarm panel."""
        self._state = None
        self._changed_by = None

        self.contractId = contractId
        self._auth = auth

    @property
    def name(self):
        """Return the name of the device."""
        return f"contract {self.contractId}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_AWAY

    async def async_update(self):
        """Update alarm status."""

        self._installation = await Installation.retrieve(self._auth)
        if self._installation.status == Status.DISARMED:
            self._state = STATE_ALARM_DISARMED
        elif self._installation.status == Status.ARMED:
            self._state = STATE_ALARM_ARMED_AWAY

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self._installation.disarm()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._installation.sarm()
