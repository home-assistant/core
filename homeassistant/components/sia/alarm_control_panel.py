"""Module for SIA Alarm Control Panels."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from pysiaalarm import SIAEvent

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ACCOUNT, CONF_ACCOUNTS, CONF_ZONES, KEY_ALARM, PREVIOUS_STATE
from .entity import SIABaseEntity, SIAEntityDescription

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
        "PA": AlarmControlPanelEntityState.TRIGGERED,
        "JA": AlarmControlPanelEntityState.TRIGGERED,
        "TA": AlarmControlPanelEntityState.TRIGGERED,
        "BA": AlarmControlPanelEntityState.TRIGGERED,
        "HA": AlarmControlPanelEntityState.TRIGGERED,
        "CA": AlarmControlPanelEntityState.ARMED_AWAY,
        "CB": AlarmControlPanelEntityState.ARMED_AWAY,
        "CG": AlarmControlPanelEntityState.ARMED_AWAY,
        "CL": AlarmControlPanelEntityState.ARMED_AWAY,
        "CP": AlarmControlPanelEntityState.ARMED_AWAY,
        "CQ": AlarmControlPanelEntityState.ARMED_AWAY,
        "CS": AlarmControlPanelEntityState.ARMED_AWAY,
        "CF": AlarmControlPanelEntityState.ARMED_CUSTOM_BYPASS,
        "NP": AlarmControlPanelEntityState.DISARMED,
        "NO": AlarmControlPanelEntityState.DISARMED,
        "OA": AlarmControlPanelEntityState.DISARMED,
        "OB": AlarmControlPanelEntityState.DISARMED,
        "OG": AlarmControlPanelEntityState.DISARMED,
        "OP": AlarmControlPanelEntityState.DISARMED,
        "OQ": AlarmControlPanelEntityState.DISARMED,
        "OR": AlarmControlPanelEntityState.DISARMED,
        "OS": AlarmControlPanelEntityState.DISARMED,
        "NC": AlarmControlPanelEntityState.ARMED_NIGHT,
        "NL": AlarmControlPanelEntityState.ARMED_NIGHT,
        "NE": AlarmControlPanelEntityState.ARMED_NIGHT,
        "NF": AlarmControlPanelEntityState.ARMED_NIGHT,
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

        self._attr_alarm_state: AlarmControlPanelEntityState | None = None
        self._old_state: AlarmControlPanelEntityState | None = None

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
        if TYPE_CHECKING:
            assert isinstance(new_state, AlarmControlPanelEntityState)
        self._attr_alarm_state, self._old_state = new_state, self._attr_alarm_state
        return True
