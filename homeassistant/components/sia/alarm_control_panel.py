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
    KEY_ALARM,
    PREVIOUS_STATE,
    SIA_NAME_FORMAT,
    SIA_UNIQUE_ID_FORMAT_ALARM,
)
from .sia_entity_base import SIABaseEntity, SIAEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
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
            port=entry.data[CONF_PORT],
            account=account_data[CONF_ACCOUNT],
            zone=zone,
            ping_interval=account_data[CONF_PING_INTERVAL],
            entity_description=ENTITY_DESCRIPTION_ALARM,
            unique_id=SIA_UNIQUE_ID_FORMAT_ALARM.format(
                entry.entry_id, account_data[CONF_ACCOUNT], zone
            ),
            name=SIA_NAME_FORMAT.format(
                entry.data[CONF_PORT], account_data[CONF_ACCOUNT], zone, "alarm"
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
    _attr_supported_features = 0

    def __init__(
        self,
        port: int,
        account: str,
        zone: int | None,
        ping_interval: int,
        entity_description: SIAAlarmControlPanelEntityDescription,
        unique_id: str,
        name: str,
    ) -> None:
        """Create SIAAlarmControlPanel object."""
        super().__init__(
            port,
            account,
            zone,
            ping_interval,
            entity_description,
            unique_id,
            name,
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

        Return True if the interval callback needs to be updated.
        """
        new_state = self.entity_description.code_consequences.get(sia_event.code)
        if new_state is None:
            return False
        _LOGGER.debug("New state will be %s", new_state)
        if new_state == PREVIOUS_STATE:
            new_state = self._old_state
        self._attr_state, self._old_state = new_state, self._attr_state
        return True
