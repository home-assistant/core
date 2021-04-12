"""Module for SIA Alarm Control Panels."""

import logging
from typing import Callable

from pysiaalarm import SIAEvent

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
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DATA_UPDATED,
    DOMAIN,
    EVENT_ACCOUNT,
    EVENT_CODE,
    EVENT_ID,
    EVENT_MESSAGE,
    EVENT_TIMESTAMP,
    EVENT_ZONE,
    PING_INTERVAL_MARGIN,
    SIA_EVENT,
)
from .utils import get_attr_from_sia_event, get_entity_and_name, get_ping_interval

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
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable[[], None]
) -> bool:
    """Set up SIA alarm_control_panel(s) from a config entry."""
    async_add_entities(
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

        self._is_available = True
        self._remove_unavailability_tracker = None
        self._state = None
        self._old_state = None
        self._attr = {
            CONF_ACCOUNT: self._account,
            CONF_PING_INTERVAL: self.ping_interval,
            CONF_ZONE: self._zone,
            EVENT_ACCOUNT: None,
            EVENT_CODE: None,
            EVENT_ID: None,
            EVENT_ZONE: None,
            EVENT_MESSAGE: None,
            EVENT_TIMESTAMP: None,
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
        async_dispatcher_connect(self.hass, DATA_UPDATED, self.async_write_ha_state)
        self.setup_sia_alarm()

    def setup_sia_alarm(self):
        """Run the setup of the alarm control panel."""
        self.assume_available()
        self._unsub = self.hass.bus.async_listen(
            self._event_listener_str, self.async_handle_event
        )
        self.async_on_remove(self._async_sia_on_remove)

    @callback
    def _async_sia_on_remove(self):
        """Remove the unavailability and event listener."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        if self._unsub:
            self._unsub()

    async def async_handle_event(self, event: Event):
        """Listen to events for this port and account and update states.

        If the port and account combo receives any message it means it is online and can therefore be set to available.
        """
        if not self.enabled:
            return
        sia_event = SIAEvent.from_dict(event.data)  # pylint: disable=no-member
        new_state = CODE_CONSEQUENCES.get(sia_event.code)
        if int(sia_event.ri) == self._zone:
            if new_state is not None:
                self.state = new_state
            self._attr.update(get_attr_from_sia_event(sia_event))
        self.assume_available()
        self.async_write_ha_state()

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

    @callback
    def _async_track_unavailable(self):
        """Reset unavailability."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()

        self._remove_unavailability_tracker = async_track_time_interval(
            self.hass,
            self.async_set_unavailable,
            self._ping_interval + PING_INTERVAL_MARGIN,
        )

        if not self._is_available:
            self._is_available = True
            self.async_schedule_update_ha_state()

    @callback
    def async_set_unavailable(self, _):
        """Set availability."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._is_available = False
        self.async_schedule_update_ha_state()

    def assume_available(self):
        """Reset unavalability tracker."""
        if self.enabled:
            self._async_track_unavailable()

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
