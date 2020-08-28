"""Module for SIA Alarm Control Panels."""

import logging
from typing import Callable

from homeassistant.components.alarm_control_panel import (
    ENTITY_ID_FORMAT as ALARM_FORMAT,
    AlarmControlPanelEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ZONE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.dt import utcnow

from .const import (
    CONF_ACCOUNT,
    CONF_PING_INTERVAL,
    DATA_UPDATED,
    DOMAIN,
    HUB_SENSOR_NAME,
    PING_INTERVAL_MARGIN,
    PREVIOUS_STATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, entry: ConfigEntry, async_add_devices: Callable[[], None]
) -> bool:
    """Set up sia_alarm_control_panel from a config entry."""
    devices = [
        device
        for device in hass.data[DOMAIN][entry.entry_id].states.values()
        if isinstance(device, SIAAlarmControlPanel)
    ]
    async_add_devices(devices)

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
        self._should_poll = False
        self._account = account
        self.entity_id = ALARM_FORMAT.format(entity_id)
        self._unique_id = entity_id
        self._name = name
        self._zone = zone
        self._ping_interval = ping_interval
        self._port = port

        self._is_available = True
        self._remove_unavailability_tracker = None
        self._state = None
        self._old_state = None
        self._attr = {
            HUB_SENSOR_NAME: None,
            CONF_ACCOUNT: self._account,
            CONF_PING_INTERVAL: str(self._ping_interval),
            CONF_ZONE: self._zone,
        }
        self._is_available = True
        self._remove_unavailability_tracker = None
        self._state = None
        self._old_state = None

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

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    @property
    def name(self) -> str:
        """Get Name."""
        return self._name

    @property
    def account(self) -> str:
        """Get Account."""
        return self._account

    @property
    def state(self) -> str:
        """Get state."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Get unique_id."""
        return self._unique_id

    @property
    def available(self) -> bool:
        """Get availability."""
        return self._is_available

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def device_state_attributes(self) -> dict:
        """Return device attributes."""
        return self._attr

    def update_attribute(self, attr: dict):
        """Update attributes."""
        self._attr.update(attr)

    @state.setter
    def state(self, state: str):
        """Set state."""
        temp = self._old_state if state == PREVIOUS_STATE else state
        self._old_state = self._state
        self._state = temp
        if not self.registry_entry.disabled:
            self.async_schedule_update_ha_state()

    async def assume_available(self):
        """Reset unavalability tracker."""
        if not self.registry_entry.disabled:
            await self._async_track_unavailable()

    @callback
    async def _async_track_unavailable(self) -> bool:
        """Reset unavailability."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        if self.hass:
            self._remove_unavailability_tracker = async_track_point_in_utc_time(
                self.hass,
                self._async_set_unavailable,
                utcnow() + self._ping_interval + PING_INTERVAL_MARGIN,
            )
        if not self._is_available:
            self._is_available = True
            return True
        return False

    @callback
    def _async_set_unavailable(self, _):
        """Set availability."""
        self._remove_unavailability_tracker = None
        self._is_available = False
        _LOGGER.debug(
            "Setting entity: %s unavailable, last heartbeat was: %s",
            self.entity_id,
            self._attr["last_heartbeat"],
        )
        self.async_schedule_update_ha_state()

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return None

    @property
    def device_info(self) -> dict:
        """Return the device_info."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self.name,
            "via_device": (DOMAIN, self._port, self._account),
        }
