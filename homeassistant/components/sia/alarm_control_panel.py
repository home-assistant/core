"""Module for SIA Alarm Control Panels."""

import logging
from typing import Callable

from homeassistant.components.alarm_control_panel import (
    ENTITY_ID_FORMAT as ALARM_FORMAT,
    AlarmControlPanelEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PORT,
    CONF_ZONE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_LAST_CODE,
    ATTR_LAST_MESSAGE,
    ATTR_LAST_TIMESTAMP,
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DATA_UPDATED,
    DOMAIN,
    EVENT_CODE,
    EVENT_MESSAGE,
    EVENT_TIMESTAMP,
    EVENT_ZONE,
    PING_INTERVAL_MARGIN,
    SIA_EVENT,
)
from .helpers import get_entity_and_name, get_ping_interval

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_ALARM = "alarm"
PREVIOUS_STATE = "previous_state"

CODE_CONSEQUENCES = {
    "PA": STATE_ALARM_TRIGGERED,
    "JA": STATE_ALARM_TRIGGERED,
    "TA": STATE_ALARM_TRIGGERED,
    "BA": STATE_ALARM_TRIGGERED,
    "CA": STATE_ALARM_ARMED_AWAY,
    "CG": STATE_ALARM_ARMED_AWAY,
    "CL": STATE_ALARM_ARMED_AWAY,
    "CP": STATE_ALARM_ARMED_AWAY,
    "CQ": STATE_ALARM_ARMED_AWAY,
    "CS": STATE_ALARM_ARMED_AWAY,
    "CF": STATE_ALARM_ARMED_CUSTOM_BYPASS,
    "OA": STATE_ALARM_DISARMED,
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
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: Callable[[], None]
) -> bool:
    """Set up SIA alarm_control_panel(s) from a config entry."""
    async_add_devices(
        [
            SIAAlarmControlPanel(
                *get_entity_and_name(
                    entry.data[CONF_PORT], acc[CONF_ACCOUNT], zone, DEVICE_CLASS_ALARM
                ),
                entry.data[CONF_PORT],
                acc[CONF_ACCOUNT],
                zone,
                acc[CONF_PING_INTERVAL],
            )
            for acc in entry.data[CONF_ACCOUNTS]
            for zone in range(1, acc[CONF_ZONES] + 1)
        ]
    )
    return True


class SIAAlarmControlPanel(AlarmControlPanelEntity, RestoreEntity):
    """Class for SIA Alarm Control Panels."""

    def __init__(
        self,
        entity_id: str,
        name: str,
        port: int,
        account: str,
        zone: int,
        ping_interval: int,
    ):
        """Create SIAAlarmControlPanel object."""
        self.entity_id = ALARM_FORMAT.format(entity_id)
        self._unique_id = entity_id
        self._name = name
        self._port = port
        self._account = account
        self._zone = zone
        self._ping_interval = get_ping_interval(ping_interval)
        self._event_listener_str = f"{SIA_EVENT}_{port}_{account}"
        self._unsub = None

        self._should_poll = False
        self._is_available = True
        self._remove_unavailability_tracker = None
        self._state = None
        self._old_state = None
        self._attr = {
            CONF_ACCOUNT: self._account,
            CONF_PING_INTERVAL: self.ping_interval,
            CONF_ZONE: self._zone,
            ATTR_LAST_MESSAGE: None,
            ATTR_LAST_CODE: None,
            ATTR_LAST_TIMESTAMP: None,
        }

    async def async_added_to_hass(self):
        """Once the panel is added, see if it was there before and pull in that state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        _LOGGER.debug(
            "Loading last state: %s",
            state.state if state is not None and state.state is not None else "None",
        )
        if (
            state is not None
            and state.state is not None
            and state.state
            in [
                STATE_ALARM_ARMED_AWAY,
                STATE_ALARM_ARMED_CUSTOM_BYPASS,
                STATE_ALARM_ARMED_NIGHT,
                STATE_ALARM_DISARMED,
                STATE_ALARM_TRIGGERED,
                STATE_UNKNOWN,
            ]
        ):
            self.state = state.state
        else:
            self.state = None
        await self._async_track_unavailable()
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )
        self._unsub = self.hass.bus.async_listen(
            self._event_listener_str, self.async_handle_event
        )
        self.async_on_remove(self._sia_on_remove)

    @callback
    def _sia_on_remove(self):
        """Remove the unavailability and event listener."""
        if self._unsub:
            self._unsub()
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()

    async def async_handle_event(self, event: Event):
        """Listen to events for this port and account and update states.

        If the port and account combo receives any message it means it is online and can therefore be set to available.
        """
        await self.assume_available()
        if int(event.data[EVENT_ZONE]) == self._zone:
            new_state = CODE_CONSEQUENCES.get(event.data[EVENT_CODE])
            if new_state:
                self._attr.update(
                    {
                        ATTR_LAST_MESSAGE: event.data[EVENT_MESSAGE],
                        ATTR_LAST_CODE: event.data[EVENT_CODE],
                        ATTR_LAST_TIMESTAMP: event.data[EVENT_TIMESTAMP],
                    }
                )
                self.state = new_state
                if not self.registry_entry.disabled:
                    self.async_schedule_update_ha_state()

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    @property
    def name(self) -> str:
        """Get Name."""
        return self._name

    @property
    def ping_interval(self) -> int:
        """Get ping_interval."""
        return str(self._ping_interval)

    @property
    def state(self) -> str:
        """Get state."""
        return self._state

    @property
    def account(self) -> str:
        """Return device account."""
        return self._account

    @property
    def unique_id(self) -> str:
        """Get unique_id."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Get availability."""
        return self._is_available

    @property
    def device_state_attributes(self) -> dict:
        """Return device attributes."""
        return self._attr

    @property
    def should_poll(self) -> bool:
        """Return False if entity pushes its state to HA."""
        return False

    @state.setter
    def state(self, state: str):
        """Set state."""
        temp = self._old_state if state == PREVIOUS_STATE else state
        self._old_state = self._state
        self._state = temp

    async def assume_available(self):
        """Reset unavalability tracker."""
        if not self.registry_entry.disabled:
            await self._async_track_unavailable()

    @callback
    async def _async_track_unavailable(self) -> bool:
        """Reset unavailability."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._remove_unavailability_tracker = async_track_point_in_utc_time(
            self.hass,
            self._async_set_unavailable,
            utcnow() + self._ping_interval + PING_INTERVAL_MARGIN,
        )
        if not self._is_available:
            self._is_available = True
            self.async_schedule_update_ha_state()
            return True
        return False

    @callback
    def _async_set_unavailable(self, _):
        """Set availability."""
        self._remove_unavailability_tracker = None
        self._is_available = False
        self.async_schedule_update_ha_state()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return None

    @property
    def device_info(self) -> dict:
        """Return the device_info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "via_device": (DOMAIN, self._port, self._account),
        }
