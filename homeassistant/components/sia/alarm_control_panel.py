"""Module for SIA Alarm Control Panels."""
from __future__ import annotations

import logging

from pysiaalarm import SIAEvent

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PORT,
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

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    SIA_UNIQUE_ID_FORMAT_ALARM,
)
from .sia_entity_base import SIABaseEntity
from .utils import SIAAlarmControlPanelEntityDescription, get_name

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_ALARM = "alarm"
PREVIOUS_STATE = "previous_state"

CODE_CONSEQUENCES: dict[str, StateType] = {
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
    "OA": STATE_ALARM_DISARMED,
    "OB": STATE_ALARM_DISARMED,
    "OG": STATE_ALARM_DISARMED,
    "OP": STATE_ALARM_DISARMED,
    "OQ": STATE_ALARM_DISARMED,
    "OR": STATE_ALARM_DISARMED,
    "OS": STATE_ALARM_DISARMED,
    "NC": STATE_ALARM_ARMED_NIGHT,
    "NL": STATE_ALARM_ARMED_NIGHT,
    "BR": PREVIOUS_STATE,
    "NP": PREVIOUS_STATE,
    "NO": PREVIOUS_STATE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SIA alarm_control_panel(s) from a config entry."""
    async_add_entities(
        SIAAlarmControlPanel(
            SIAAlarmControlPanelEntityDescription(
                key=SIA_UNIQUE_ID_FORMAT_ALARM.format(
                    entry.entry_id, account_data[CONF_ACCOUNT], zone
                ),
                device_class=DEVICE_CLASS_ALARM,
                name=get_name(
                    port=entry.data[CONF_PORT],
                    account=account_data[CONF_ACCOUNT],
                    zone=zone,
                    device_class=DEVICE_CLASS_ALARM,
                ),
                port=entry.data[CONF_PORT],
                account=account_data[CONF_ACCOUNT],
                zone=zone,
                ping_interval=account_data[CONF_PING_INTERVAL],
                code_consequences=CODE_CONSEQUENCES,
            ),
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
        entity_description: SIAAlarmControlPanelEntityDescription,
    ) -> None:
        """Create SIAAlarmControlPanel object."""
        super().__init__()
        self.entity_description = entity_description

        self._attr_state: StateType = None
        self._old_state: StateType = None
        self._attr_supported_features = 0

    def update_state(self, sia_event: SIAEvent) -> None:
        """Update the state of the alarm control panel."""
        new_state = self.entity_description.code_consequences.get(sia_event.code, None)
        if new_state is not None:
            _LOGGER.debug("New state will be %s", new_state)
            if new_state == PREVIOUS_STATE:
                new_state = self._old_state
            self._attr_state, self._old_state = new_state, self._attr_state

    def handle_last_state(self, last_state: State | None) -> None:
        """Handle the last state."""
        if last_state is not None:
            self._attr_state = last_state.state
        if self.state == STATE_UNAVAILABLE:
            self._attr_available = False
