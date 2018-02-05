"""
Group platform for alarm control panel component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.group/
"""
import asyncio
from collections import Counter
from copy import deepcopy
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import (
    DOMAIN, PLATFORM_SCHEMA, SERVICE_ALARM_DISARM, SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_AWAY, SERVICE_ALARM_ARM_NIGHT, SERVICE_ALARM_TRIGGER,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_PRE_PENDING_STATE, ATTR_POST_PENDING_STATE,
    CONF_NAME, EVENT_HOMEASSISTANT_START,
    STATE_ALARM_ARMED_CUSTOM_BYPASS, STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change

ATTR_TRIGGERED_PANELS = 'triggered_panels'

CONF_CODE_FORMAT = 'code_format'
CONF_PANELS = 'panels'
CONF_PANEL = 'panel'

DEFAULT_ALARM_NAME = 'Group Alarm'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_ALARM_NAME): cv.string,
    vol.Optional(CONF_CODE_FORMAT, default=''): cv.string,
    vol.Required(CONF_PANELS): vol.All(cv.ensure_list, [{
        vol.Required(CONF_PANEL): cv.entity_id,
    }])
})

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the group alarm platform."""
    add_devices([GroupAlarm(
        hass,
        config[CONF_NAME],
        config[CONF_CODE_FORMAT],
        config[CONF_PANELS]
        )])


class GroupAlarm(alarm.AlarmControlPanel):
    """Implement services and state computation for the group alarm platform."""

    def __init__(self, hass, name, code_format, entities):
        """Initialize the platform."""
        self._hass = hass
        self._name = name
        self._code_format = code_format if code_format else None
        self._entity_ids = [entity.get(CONF_PANEL) for entity in entities]
        self._triggered_panels = []
        self._state = STATE_ALARM_DISARMED
        self._pre_state = self._state
        self._post_state = self._state

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def group_alarm_state_listener(entity, old_state, new_state):
            """Handle device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def group_alarm_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, self._entity_ids, group_alarm_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, group_alarm_startup)

    @asyncio.coroutine
    def _async_send_message(self, service, **kwargs):
        """Send message to all entities in the group."""
        payload = {key: val for key, val in kwargs.items() if val}

        tasks = []
        for entity_id in self._entity_ids:
            sending_payload = deepcopy(payload.copy())
            sending_payload[ATTR_ENTITY_ID] = entity_id
            tasks.append(self.hass.services.async_call(
                DOMAIN, service, sending_payload))

        if tasks:
            yield from asyncio.wait(tasks, loop=self.hass.loop)

    @property
    def name(self):
        """Return the name of the control panel."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def code_format(self):
        """The code format is customizable."""
        return self._code_format

    @asyncio.coroutine
    def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        yield from self._async_send_message(SERVICE_ALARM_DISARM,
                                            code=code)

    @asyncio.coroutine
    def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        yield from self._async_send_message(SERVICE_ALARM_ARM_HOME,
                                            code=code)

    @asyncio.coroutine
    def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        yield from self._async_send_message(SERVICE_ALARM_ARM_AWAY,
                                            code=code)

    @asyncio.coroutine
    def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        yield from self._async_send_message(SERVICE_ALARM_ARM_NIGHT,
                                            code=code)

    @asyncio.coroutine
    def async_alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        yield from self._async_send_message(SERVICE_ALARM_TRIGGER,
                                            code=code)

    @asyncio.coroutine
    def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        yield from self._async_send_message(SERVICE_ALARM_ARM_CUSTOM_BYPASS,
                                            code=code)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @asyncio.coroutine
    def async_update(self):
        """Update the current state and state attributes of the device."""
        def _common_state(states):
            # This can happen if the sub-panels have not loaded yet.
            if len(states) == 0:
                return STATE_ALARM_DISARMED

            # One triggered sub-panel is enough to trigger the whole panel.
            if states[STATE_ALARM_TRIGGERED]:
                return STATE_ALARM_TRIGGERED

            # This only happens if a member does not provide pre or
            # post_pending_state.  In that case, ensure the pending state
            # percolates up to device_state_attributes, and the attribute
            # will be left out in the group as well.
            if states[STATE_ALARM_PENDING]:
                return STATE_ALARM_PENDING

            # If all entities have the same state, great. Otherwise,
            # we can only summarize the state as "custom bypass".
            if len(states) == 1:
                return next(iter(states))
            return STATE_ALARM_ARMED_CUSTOM_BYPASS

        # First collect the pre- and post-states for all devices.
        self._triggered_panels = []
        pre_states = Counter()
        post_states = Counter()
        for entity_id, state in self._states:
            if state.state == STATE_ALARM_PENDING and \
                    (ATTR_PRE_PENDING_STATE in state.attributes):
                pre_state = state.attributes[ATTR_PRE_PENDING_STATE]
            else:
                pre_state = state.state

            if state.state == STATE_ALARM_PENDING and \
                    (ATTR_POST_PENDING_STATE in state.attributes):
                post_state = state.attributes[ATTR_POST_PENDING_STATE]
            else:
                post_state = state.state

            if pre_state == STATE_ALARM_TRIGGERED:
                self._triggered_panels.append(entity_id)
            pre_states[pre_state] += 1
            post_states[post_state] += 1

        # Now find the pre- and post-state for the entire group.
        self._pre_state = _common_state(pre_states)
        self._post_state = _common_state(post_states)
        if self._pre_state == self._post_state:
            self._state = self._post_state
        else:
            self._state = STATE_ALARM_PENDING

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}

        if self._state == STATE_ALARM_TRIGGERED:
            state_attr[ATTR_TRIGGERED_PANELS] = self._triggered_panels

        if self._state == STATE_ALARM_PENDING:
            # If the pre or post state is pending, the sub-entities are
            # not able to provide accurate pre/post-state information;
            # leave out the attribute
            if self._pre_state != STATE_ALARM_PENDING:
                state_attr[ATTR_PRE_PENDING_STATE] = self._pre_state
            if self._post_state != STATE_ALARM_PENDING:
                state_attr[ATTR_POST_PENDING_STATE] = self._post_state

        return state_attr

    @property
    def _states(self):
        for entity_id in self._entity_ids:
            state_obj = self.hass.states.get(entity_id)
            if state_obj is not None:
                yield entity_id, state_obj
