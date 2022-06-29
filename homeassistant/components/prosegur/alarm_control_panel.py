"""Support for Prosegur alarm control panels."""
from __future__ import annotations

import logging

from pyprosegur.auth import Auth
from pyprosegur.installation import Installation, Status

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

STATE_MAPPING = {
    Status.DISARMED: STATE_ALARM_DISARMED,
    Status.ARMED: STATE_ALARM_ARMED_AWAY,
    Status.PARTIALLY: STATE_ALARM_ARMED_HOME,
    Status.ERROR_PARTIALLY: STATE_ALARM_ARMED_HOME,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Prosegur alarm control panel platform."""
    async_add_entities(
        [ProsegurAlarm(entry.data["contract"], hass.data[DOMAIN][entry.entry_id])],
        update_before_add=True,
    )


class ProsegurAlarm(alarm.AlarmControlPanelEntity):
    """Representation of a Prosegur alarm status."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
    )
    _installation: Installation

    def __init__(self, contract: str, auth: Auth) -> None:
        """Initialize the Prosegur alarm panel."""
        self._changed_by = None

        self.contract = contract
        self._auth = auth

        self._attr_code_arm_required = False
        self._attr_name = f"contract {self.contract}"
        self._attr_unique_id = self.contract

    async def async_update(self) -> None:
        """Update alarm status."""

        try:
            self._installation = await Installation.retrieve(self._auth)
        except ConnectionError as err:
            _LOGGER.error(err)
            self._attr_available = False
            return

        self._attr_state = STATE_MAPPING.get(self._installation.status)
        self._attr_available = True

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._installation.disarm(self._auth)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._installation.arm_partially(self._auth)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._installation.arm(self._auth)
