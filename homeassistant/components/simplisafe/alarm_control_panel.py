"""Support for SimpliSafe alarm control panels."""
from __future__ import annotations

from typing import TYPE_CHECKING

from simplipy.errors import SimplipyError
from simplipy.system import SystemStates
from simplipy.system.v2 import SystemV2
from simplipy.system.v3 import (
    VOLUME_HIGH,
    VOLUME_LOW,
    VOLUME_MEDIUM,
    VOLUME_OFF,
    SystemV3,
)
from simplipy.websocket import (
    EVENT_ALARM_CANCELED,
    EVENT_ALARM_TRIGGERED,
    EVENT_ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_KEYPAD,
    EVENT_ARMED_AWAY_BY_REMOTE,
    EVENT_ARMED_HOME,
    EVENT_AWAY_EXIT_DELAY_BY_KEYPAD,
    EVENT_AWAY_EXIT_DELAY_BY_REMOTE,
    EVENT_DISARMED_BY_MASTER_PIN,
    EVENT_DISARMED_BY_REMOTE,
    EVENT_HOME_EXIT_DELAY,
    WebsocketEvent,
)

from homeassistant.components.alarm_control_panel import (
    FORMAT_NUMBER,
    FORMAT_TEXT,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CODE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafe, SimpliSafeEntity
from .const import (
    ATTR_ALARM_DURATION,
    ATTR_ALARM_VOLUME,
    ATTR_CHIME_VOLUME,
    ATTR_ENTRY_DELAY_AWAY,
    ATTR_ENTRY_DELAY_HOME,
    ATTR_EXIT_DELAY_AWAY,
    ATTR_EXIT_DELAY_HOME,
    ATTR_LIGHT,
    ATTR_VOICE_PROMPT_VOLUME,
    DATA_CLIENT,
    DOMAIN,
    LOGGER,
)

ATTR_BATTERY_BACKUP_POWER_LEVEL = "battery_backup_power_level"
ATTR_GSM_STRENGTH = "gsm_strength"
ATTR_PIN_NAME = "pin_name"
ATTR_RF_JAMMING = "rf_jamming"
ATTR_WALL_POWER_LEVEL = "wall_power_level"
ATTR_WIFI_STRENGTH = "wifi_strength"

DEFAULT_ERRORS_TO_ACCOMMODATE = 2

VOLUME_STRING_MAP = {
    VOLUME_HIGH: "high",
    VOLUME_LOW: "low",
    VOLUME_MEDIUM: "medium",
    VOLUME_OFF: "off",
}

STATE_MAP_FROM_REST_API = {
    SystemStates.alarm: STATE_ALARM_TRIGGERED,
    SystemStates.away: STATE_ALARM_ARMED_AWAY,
    SystemStates.away_count: STATE_ALARM_ARMING,
    SystemStates.exit_delay: STATE_ALARM_ARMING,
    SystemStates.home: STATE_ALARM_ARMED_HOME,
    SystemStates.off: STATE_ALARM_DISARMED,
}

STATE_MAP_FROM_WEBSOCKET_EVENT = {
    EVENT_ALARM_CANCELED: STATE_ALARM_DISARMED,
    EVENT_ALARM_TRIGGERED: STATE_ALARM_TRIGGERED,
    EVENT_ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_KEYPAD: STATE_ALARM_ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_REMOTE: STATE_ALARM_ARMED_AWAY,
    EVENT_ARMED_HOME: STATE_ALARM_ARMED_HOME,
    EVENT_AWAY_EXIT_DELAY_BY_KEYPAD: STATE_ALARM_ARMING,
    EVENT_AWAY_EXIT_DELAY_BY_REMOTE: STATE_ALARM_ARMING,
    EVENT_DISARMED_BY_MASTER_PIN: STATE_ALARM_DISARMED,
    EVENT_DISARMED_BY_REMOTE: STATE_ALARM_DISARMED,
    EVENT_HOME_EXIT_DELAY: STATE_ALARM_ARMING,
}

WEBSOCKET_EVENTS_TO_LISTEN_FOR = (
    EVENT_ALARM_CANCELED,
    EVENT_ALARM_TRIGGERED,
    EVENT_ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_KEYPAD,
    EVENT_ARMED_AWAY_BY_REMOTE,
    EVENT_ARMED_HOME,
    EVENT_AWAY_EXIT_DELAY_BY_KEYPAD,
    EVENT_AWAY_EXIT_DELAY_BY_REMOTE,
    EVENT_DISARMED_BY_MASTER_PIN,
    EVENT_DISARMED_BY_REMOTE,
    EVENT_HOME_EXIT_DELAY,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a SimpliSafe alarm control panel based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    async_add_entities(
        [SimpliSafeAlarm(simplisafe, system) for system in simplisafe.systems.values()],
        True,
    )


class SimpliSafeAlarm(SimpliSafeEntity, AlarmControlPanelEntity):
    """Representation of a SimpliSafe alarm."""

    def __init__(self, simplisafe: SimpliSafe, system: SystemV2 | SystemV3) -> None:
        """Initialize the SimpliSafe alarm."""
        super().__init__(
            simplisafe,
            system,
            additional_websocket_events=WEBSOCKET_EVENTS_TO_LISTEN_FOR,
        )

        self._errors = 0

        if code := self._simplisafe.entry.options.get(CONF_CODE):
            if code.isdigit():
                self._attr_code_format = FORMAT_NUMBER
            else:
                self._attr_code_format = FORMAT_TEXT
        self._attr_supported_features = SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY
        self._last_event = None

        if system.alarm_going_off:
            self._attr_state = STATE_ALARM_TRIGGERED
        elif system.state == SystemStates.away:
            self._attr_state = STATE_ALARM_ARMED_AWAY
        elif system.state in (
            SystemStates.away_count,
            SystemStates.exit_delay,
            SystemStates.home_count,
        ):
            self._attr_state = STATE_ALARM_ARMING
        elif system.state == SystemStates.home:
            self._attr_state = STATE_ALARM_ARMED_HOME
        elif system.state == SystemStates.off:
            self._attr_state = STATE_ALARM_DISARMED
        else:
            self._attr_state = None

    @callback
    def _is_code_valid(self, code: str | None, state: str) -> bool:
        """Validate that a code matches the required one."""
        if not self._simplisafe.entry.options.get(CONF_CODE):
            return True

        if not code or code != self._simplisafe.entry.options[CONF_CODE]:
            LOGGER.warning(
                "Incorrect alarm code entered (target state: %s): %s", state, code
            )
            return False

        return True

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        if not self._is_code_valid(code, STATE_ALARM_DISARMED):
            return

        try:
            await self._system.async_set_off()
        except SimplipyError as err:
            LOGGER.error('Error while disarming "%s": %s', self._system.system_id, err)
            return

        self._attr_state = STATE_ALARM_DISARMED
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        if not self._is_code_valid(code, STATE_ALARM_ARMED_HOME):
            return

        try:
            await self._system.async_set_home()
        except SimplipyError as err:
            LOGGER.error(
                'Error while arming "%s" (home): %s', self._system.system_id, err
            )
            return

        self._attr_state = STATE_ALARM_ARMED_HOME
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        if not self._is_code_valid(code, STATE_ALARM_ARMED_AWAY):
            return

        try:
            await self._system.async_set_away()
        except SimplipyError as err:
            LOGGER.error(
                'Error while arming "%s" (away): %s', self._system.system_id, err
            )
            return

        self._attr_state = STATE_ALARM_ARMING
        self.async_write_ha_state()

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        if isinstance(self._system, SystemV3):
            self._attr_extra_state_attributes.update(
                {
                    ATTR_ALARM_DURATION: self._system.alarm_duration,
                    ATTR_ALARM_VOLUME: VOLUME_STRING_MAP[self._system.alarm_volume],
                    ATTR_BATTERY_BACKUP_POWER_LEVEL: self._system.battery_backup_power_level,
                    ATTR_CHIME_VOLUME: VOLUME_STRING_MAP[self._system.chime_volume],
                    ATTR_ENTRY_DELAY_AWAY: self._system.entry_delay_away,
                    ATTR_ENTRY_DELAY_HOME: self._system.entry_delay_home,
                    ATTR_EXIT_DELAY_AWAY: self._system.exit_delay_away,
                    ATTR_EXIT_DELAY_HOME: self._system.exit_delay_home,
                    ATTR_GSM_STRENGTH: self._system.gsm_strength,
                    ATTR_LIGHT: self._system.light,
                    ATTR_RF_JAMMING: self._system.rf_jamming,
                    ATTR_VOICE_PROMPT_VOLUME: VOLUME_STRING_MAP[
                        self._system.voice_prompt_volume
                    ],
                    ATTR_WALL_POWER_LEVEL: self._system.wall_power_level,
                    ATTR_WIFI_STRENGTH: self._system.wifi_strength,
                }
            )

        # SimpliSafe can incorrectly return an error state when there isn't any
        # error. This can lead to the system having an unknown state frequently.
        # To protect against that, we measure how many "error states" we receive
        # and only alter the state if we detect a few in a row:
        if self._system.state == SystemStates.error:
            if self._errors > DEFAULT_ERRORS_TO_ACCOMMODATE:
                self._attr_state = None
            else:
                self._errors += 1
            return

        self._errors = 0

        if state := STATE_MAP_FROM_REST_API.get(self._system.state):
            self._attr_state = state
        else:
            LOGGER.error("Unknown system state (REST API): %s", self._system.state)
            self._attr_state = None

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        self._attr_changed_by = event.changed_by
        if TYPE_CHECKING:
            assert event.event_type
        self._attr_state = STATE_MAP_FROM_WEBSOCKET_EVENT.get(event.event_type)
