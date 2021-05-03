"""Module for SIA Alarm Control Panels."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any, Callable

from pysiaalarm import SIAEvent

from homeassistant.components.alarm_control_panel import (
    DOMAIN as AlarmDomain,
    ENTITY_ID_FORMAT,
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
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    CONF_PING_INTERVAL,
    CONF_ZONES,
    DOMAIN,
    PING_INTERVAL_MARGIN,
    SIA_EVENT,
)
from .utils import get_attr_from_sia_event, get_id_and_name, get_ping_interval

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
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[..., None],
) -> bool:
    """Set up SIA alarm_control_panel(s) from a config entry."""
    async_add_entities(
        [
            SIAAlarmControlPanel(
                *get_id_and_name(
                    entry.data[CONF_PORT], acc[CONF_ACCOUNT], DEVICE_CLASS_ALARM, zone
                ),
                entry,
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
        entry: ConfigEntry,
        account: str,
        zone: int,
        ping_interval: int,
    ):
        """Create SIAAlarmControlPanel object."""
        self._unique_id: str = f"{entry.entry_id}_{account}_{zone}_{AlarmDomain}"
        self.entity_id: str = ENTITY_ID_FORMAT.format(entity_id)
        self._entry: ConfigEntry = entry
        self._name: str = name
        self._port: str = self._entry.data[CONF_PORT]
        self._account: str = account
        self._zone: int = zone
        self._ping_interval_int: int = ping_interval
        self._event_listener_str: str = SIA_EVENT.format(self._port, account)
        self._attr: dict[str, Any] = {CONF_ACCOUNT: account, CONF_ZONE: zone}

        self._is_available: bool = True

        self._ping_interval: timedelta | None = None
        self._remove_unavailability_tracker: CALLBACK_TYPE | None = None
        self._state: StateType = None
        self._old_state: StateType = None

    async def async_added_to_hass(self) -> None:
        """Once the panel is added, see if it was there before and pull in that state."""
        self._ping_interval = get_ping_interval(self._ping_interval_int)
        self._attr[CONF_PING_INTERVAL] = self.ping_interval
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
        self.async_write_ha_state()
        self.setup_sia_alarm()

    def setup_sia_alarm(self) -> None:
        """Run the setup of the alarm control panel."""
        self._async_track_unavailable()
        self.async_on_remove(
            self.hass.bus.async_listen(
                self._event_listener_str, self.async_handle_event
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        Overwritten from entity.
        """
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()

    async def async_handle_event(self, event: Event) -> None:
        """Listen to events for this port and account and update states.

        If the port and account combo receives any message it means it is online and can therefore be set to available.
        """
        if not self.enabled:
            return
        sia_event = SIAEvent.from_dict(event.data)  # pylint: disable=no-member
        if int(sia_event.ri) == self._zone:
            self.state = CODE_CONSEQUENCES.get(sia_event.code, None)
            self._attr.update(get_attr_from_sia_event(sia_event))
        self._async_track_unavailable()
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Get Name."""
        return self._name

    @property
    def ping_interval(self) -> str:
        """Get ping_interval."""
        return str(self._ping_interval)

    @property
    def state(self) -> StateType:
        """Get state."""
        return self._state

    @state.setter
    def state(self, state: str) -> None:
        """Set state."""
        if state is None:
            return
        temp = self._old_state if state == PREVIOUS_STATE else state
        self._old_state = self._state
        self._state = temp

    @property
    def unique_id(self) -> str:
        """Get unique_id."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Get availability."""
        return self._is_available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device attributes."""
        return self._attr

    @property
    def should_poll(self) -> bool:
        """Return False if entity pushes its state to HA."""
        return False

    @callback
    def _async_track_unavailable(self) -> None:
        """Reset unavailability."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        if not self.enabled:
            return

        if isinstance(self._ping_interval, timedelta):
            self._remove_unavailability_tracker = async_track_time_interval(
                self.hass,
                self.async_set_unavailable,
                self._ping_interval + PING_INTERVAL_MARGIN,
            )
            if not self._is_available:
                self._is_available = True
                self.async_schedule_update_ha_state()

    @callback
    def async_set_unavailable(self, _) -> None:
        """Set availability."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._is_available = False
        self.async_schedule_update_ha_state()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return 0

    @property
    def device_info(self) -> Mapping[str, Any] | None:
        """Return the device_info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "via_device": (DOMAIN, f"{self._port}_{self._account}"),
        }
