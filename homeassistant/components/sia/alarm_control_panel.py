"""Module for SIA Alarm Control Panels."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from pysiaalarm import SIAEvent

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CONF_ACCOUNT, CONF_ACCOUNTS, CONF_ZONES, KEY_ALARM, PREVIOUS_STATE
from .sia_entity_base import SIABaseEntity, SIAEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SIAAlarmControlPanelEntityDescription(
    AlarmControlPanelEntityDescription,
    SIAEntityDescription,
):
    """Describes SIA alarm control panel entity."""


ENTITY_DESCRIPTION_ALARM = SIAAlarmControlPanelEntityDescription(
    key=KEY_ALARM,
    code_consequences={
        "PA": STATE_ALARM_TRIGGERED,
        "JA": STATE_ALARM_TRIGGERED,
        "TA": STATE_ALARM_TRIGGERED,
        "BA": STATE_ALARM_TRIGGERED,
        "CA": STATE_ALARM_ARMED_AWAY,
        "CB": STATE_ALARM_ARMED_AWAY,
        "CG": STATE_ALARM_ARMED_AWAY,
        "CL": STATE_ALARM_ARMED_AWAY,
        "CP": STATE_ALARM_ARMED_AWAY,
        "CQ": STATE_ALARM_ARMED_AWAY,
        "CS": STATE_ALARM_ARMED_AWAY,
        "CF": STATE_ALARM_ARMED_CUSTOM_BYPASS,
        "NP": STATE_ALARM_DISARMED,
        "NO": STATE_ALARM_DISARMED,
        "OA": STATE_ALARM_DISARMED,
        "OB": STATE_ALARM_DISARMED,
        "OG": STATE_ALARM_DISARMED,
        "OP": STATE_ALARM_DISARMED,
        "OQ": STATE_ALARM_DISARMED,
        "OR": STATE_ALARM_DISARMED,
        "OS": STATE_ALARM_DISARMED,
        "NC": STATE_ALARM_ARMED_NIGHT,
        "NL": STATE_ALARM_ARMED_NIGHT,
        "NE": STATE_ALARM_ARMED_CUSTOM_BYPASS,
        "NF": STATE_ALARM_ARMED_CUSTOM_BYPASS,
        "BR": PREVIOUS_STATE,
    },
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SIA alarm_control_panel(s) from a config entry."""
    async_add_entities(
        SIAAlarmControlPanel(
            entry, account_data[CONF_ACCOUNT], zone, ENTITY_DESCRIPTION_ALARM
        )
        for account_data in entry.data[CONF_ACCOUNTS]
        for zone in range(
            1,
            entry.options[CONF_ACCOUNTS][account_data[CONF_ACCOUNT]][CONF_ZONES] + 1,
        )
    )


class SIAAlarmControlPanel(SIABaseEntity, AlarmControlPanelEntity):
    """Class for SIA Alarm Control Panels."""

    entity_description: SIAAlarmControlPanelEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        account: str,
        zone: int,
        entity_description: SIAAlarmControlPanelEntityDescription,
    ) -> None:
        """Create SIAAlarmControlPanel object."""
        super().__init__(
            entry,
            account,
            zone,
            entity_description,
        )

        self._attr_state: StateType = None
        self._old_state: StateType = None

    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""
        if last_state is not None:
            self._attr_state = last_state.state
        if self.state == STATE_UNAVAILABLE:
            self._attr_available = False

    def update_state(self, sia_event: SIAEvent) -> bool:
        """Update the state of the alarm control panel.

        Return True if the event was relevant for this entity.
        """
        new_state = None
        if sia_event.code:
            new_state = self.entity_description.code_consequences.get(sia_event.code)
        if new_state is None:
            return False
        _LOGGER.debug("New state will be %s", new_state)
        if new_state == PREVIOUS_STATE:
            new_state = self._old_state
        self._attr_state, self._old_state = new_state, self._attr_state
        return True
