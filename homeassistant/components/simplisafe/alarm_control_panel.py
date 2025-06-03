"""Support for SimpliSafe alarm control panels."""

from __future__ import annotations

from simplipy.errors import SimplipyError
from simplipy.system import SystemStates
from simplipy.system.v3 import SystemV3
from simplipy.websocket import (
    EVENT_ALARM_CANCELED,
    EVENT_ALARM_TRIGGERED,
    EVENT_ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_KEYPAD,
    EVENT_ARMED_AWAY_BY_REMOTE,
    EVENT_ARMED_HOME,
    EVENT_AWAY_EXIT_DELAY_BY_KEYPAD,
    EVENT_AWAY_EXIT_DELAY_BY_REMOTE,
    EVENT_DISARMED_BY_KEYPAD,
    EVENT_DISARMED_BY_REMOTE,
    EVENT_ENTRY_DELAY,
    EVENT_HOME_EXIT_DELAY,
    EVENT_SECRET_ALERT_TRIGGERED,
    EVENT_USER_INITIATED_TEST,
    WebsocketEvent,
)

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SimpliSafe
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
    DOMAIN,
    LOGGER,
)
from .entity import SimpliSafeEntity
from .typing import SystemType

ATTR_BATTERY_BACKUP_POWER_LEVEL = "battery_backup_power_level"
ATTR_GSM_STRENGTH = "gsm_strength"
ATTR_PIN_NAME = "pin_name"
ATTR_RF_JAMMING = "rf_jamming"
ATTR_WALL_POWER_LEVEL = "wall_power_level"
ATTR_WIFI_STRENGTH = "wifi_strength"

STATE_MAP_FROM_REST_API = {
    SystemStates.ALARM: AlarmControlPanelState.TRIGGERED,
    SystemStates.ALARM_COUNT: AlarmControlPanelState.PENDING,
    SystemStates.AWAY: AlarmControlPanelState.ARMED_AWAY,
    SystemStates.AWAY_COUNT: AlarmControlPanelState.ARMING,
    SystemStates.ENTRY_DELAY: AlarmControlPanelState.PENDING,
    SystemStates.EXIT_DELAY: AlarmControlPanelState.ARMING,
    SystemStates.HOME: AlarmControlPanelState.ARMED_HOME,
    SystemStates.HOME_COUNT: AlarmControlPanelState.ARMING,
    SystemStates.OFF: AlarmControlPanelState.DISARMED,
    SystemStates.TEST: AlarmControlPanelState.DISARMED,
}

STATE_MAP_FROM_WEBSOCKET_EVENT = {
    EVENT_ALARM_CANCELED: AlarmControlPanelState.DISARMED,
    EVENT_ALARM_TRIGGERED: AlarmControlPanelState.TRIGGERED,
    EVENT_ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_KEYPAD: AlarmControlPanelState.ARMED_AWAY,
    EVENT_ARMED_AWAY_BY_REMOTE: AlarmControlPanelState.ARMED_AWAY,
    EVENT_ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    EVENT_AWAY_EXIT_DELAY_BY_KEYPAD: AlarmControlPanelState.ARMING,
    EVENT_AWAY_EXIT_DELAY_BY_REMOTE: AlarmControlPanelState.ARMING,
    EVENT_DISARMED_BY_KEYPAD: AlarmControlPanelState.DISARMED,
    EVENT_DISARMED_BY_REMOTE: AlarmControlPanelState.DISARMED,
    EVENT_ENTRY_DELAY: AlarmControlPanelState.PENDING,
    EVENT_HOME_EXIT_DELAY: AlarmControlPanelState.ARMING,
    EVENT_SECRET_ALERT_TRIGGERED: AlarmControlPanelState.TRIGGERED,
    EVENT_USER_INITIATED_TEST: AlarmControlPanelState.DISARMED,
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
    EVENT_DISARMED_BY_KEYPAD,
    EVENT_DISARMED_BY_REMOTE,
    EVENT_HOME_EXIT_DELAY,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a SimpliSafe alarm control panel based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [SimpliSafeAlarm(simplisafe, system) for system in simplisafe.systems.values()],
        True,
    )


class SimpliSafeAlarm(SimpliSafeEntity, AlarmControlPanelEntity):
    """Representation of a SimpliSafe alarm."""

    _attr_code_arm_required = False
    _attr_name = None
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(self, simplisafe: SimpliSafe, system: SystemType) -> None:
        """Initialize the SimpliSafe alarm."""
        super().__init__(
            simplisafe,
            system,
            additional_websocket_events=WEBSOCKET_EVENTS_TO_LISTEN_FOR,
        )

        self._last_event = None
        self._set_state_from_system_data()

    @callback
    def _set_state_from_system_data(self) -> None:
        """Set the state based on the latest REST API data."""
        if self._system.alarm_going_off:
            self._attr_alarm_state = AlarmControlPanelState.TRIGGERED
        elif state := STATE_MAP_FROM_REST_API.get(self._system.state):
            self._attr_alarm_state = state
            self.async_reset_error_count()
        else:
            LOGGER.warning("Unexpected system state (REST API): %s", self._system.state)
            self.async_increment_error_count()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            await self._system.async_set_off()
        except SimplipyError as err:
            raise HomeAssistantError(
                f'Error while disarming "{self._system.system_id}": {err}'
            ) from err

        self._attr_alarm_state = AlarmControlPanelState.DISARMED
        self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        try:
            await self._system.async_set_home()
        except SimplipyError as err:
            raise HomeAssistantError(
                f'Error while arming (home) "{self._system.system_id}": {err}'
            ) from err

        self._attr_alarm_state = AlarmControlPanelState.ARMED_HOME
        self.async_write_ha_state()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        try:
            await self._system.async_set_away()
        except SimplipyError as err:
            raise HomeAssistantError(
                f'Error while arming (away) "{self._system.system_id}": {err}'
            ) from err

        self._attr_alarm_state = AlarmControlPanelState.ARMING
        self.async_write_ha_state()

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        if isinstance(self._system, SystemV3):
            self._attr_extra_state_attributes.update(
                {
                    ATTR_ALARM_DURATION: self._system.alarm_duration,
                    ATTR_BATTERY_BACKUP_POWER_LEVEL: (
                        self._system.battery_backup_power_level
                    ),
                    ATTR_ENTRY_DELAY_AWAY: self._system.entry_delay_away,
                    ATTR_ENTRY_DELAY_HOME: self._system.entry_delay_home,
                    ATTR_EXIT_DELAY_AWAY: self._system.exit_delay_away,
                    ATTR_EXIT_DELAY_HOME: self._system.exit_delay_home,
                    ATTR_GSM_STRENGTH: self._system.gsm_strength,
                    ATTR_LIGHT: self._system.light,
                    ATTR_RF_JAMMING: self._system.rf_jamming,
                    ATTR_WALL_POWER_LEVEL: self._system.wall_power_level,
                    ATTR_WIFI_STRENGTH: self._system.wifi_strength,
                }
            )

            for key, volume_prop in (
                (ATTR_ALARM_VOLUME, self._system.alarm_volume),
                (ATTR_CHIME_VOLUME, self._system.chime_volume),
                (ATTR_VOICE_PROMPT_VOLUME, self._system.voice_prompt_volume),
            ):
                if not volume_prop:
                    continue
                self._attr_extra_state_attributes[key] = volume_prop.name.lower()

        self._set_state_from_system_data()

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        self._attr_changed_by = event.changed_by

        assert event.event_type

        if state := STATE_MAP_FROM_WEBSOCKET_EVENT.get(event.event_type):
            self._attr_alarm_state = state
            self.async_reset_error_count()
        else:
            LOGGER.error("Unknown alarm websocket event: %s", event.event_type)
            self.async_increment_error_count()
