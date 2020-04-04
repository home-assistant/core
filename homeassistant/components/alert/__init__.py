"""Support for repeating alerts when conditions are met."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as DOMAIN_NOTIFY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_STATE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import event, service
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.util.dt import now

_LOGGER = logging.getLogger(__name__)

DOMAIN = "alert"

CONF_CAN_ACK = "can_acknowledge"
CONF_NOTIFIERS = "notifiers"
CONF_REPEAT = "repeat"
CONF_SKIP_FIRST = "skip_first"
CONF_ALERT_MESSAGE = "message"
CONF_DONE_MESSAGE = "done_message"
CONF_TITLE = "title"
CONF_DATA = "data"

DEFAULT_CAN_ACK = True
DEFAULT_SKIP_FIRST = False

ALERT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_STATE, default=STATE_ON): cv.string,
        vol.Required(CONF_REPEAT): vol.All(cv.ensure_list, [vol.Coerce(float)]),
        vol.Required(CONF_CAN_ACK, default=DEFAULT_CAN_ACK): cv.boolean,
        vol.Required(CONF_SKIP_FIRST, default=DEFAULT_SKIP_FIRST): cv.boolean,
        vol.Optional(CONF_ALERT_MESSAGE): cv.template,
        vol.Optional(CONF_DONE_MESSAGE): cv.template,
        vol.Optional(CONF_TITLE): cv.template,
        vol.Optional(CONF_DATA): dict,
        vol.Required(CONF_NOTIFIERS): cv.ensure_list,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(ALERT_SCHEMA)}, extra=vol.ALLOW_EXTRA
)

ALERT_SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})


def is_on(hass, entity_id):
    """Return if the alert is firing and not acknowledged."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass, config):
    """Set up the Alert component."""
    entities = []

    for object_id, cfg in config[DOMAIN].items():
        if not cfg:
            cfg = {}

        name = cfg.get(CONF_NAME)
        watched_entity_id = cfg.get(CONF_ENTITY_ID)
        alert_state = cfg.get(CONF_STATE)
        repeat = cfg.get(CONF_REPEAT)
        skip_first = cfg.get(CONF_SKIP_FIRST)
        message_template = cfg.get(CONF_ALERT_MESSAGE)
        done_message_template = cfg.get(CONF_DONE_MESSAGE)
        notifiers = cfg.get(CONF_NOTIFIERS)
        can_ack = cfg.get(CONF_CAN_ACK)
        title_template = cfg.get(CONF_TITLE)
        data = cfg.get(CONF_DATA)

        entities.append(
            Alert(
                hass,
                object_id,
                name,
                watched_entity_id,
                alert_state,
                repeat,
                skip_first,
                message_template,
                done_message_template,
                notifiers,
                can_ack,
                title_template,
                data,
            )
        )

    if not entities:
        return False

    async def async_handle_alert_service(service_call):
        """Handle calls to alert services."""
        alert_ids = await service.async_extract_entity_ids(hass, service_call)

        for alert_id in alert_ids:
            for alert in entities:
                if alert.entity_id != alert_id:
                    continue

                alert.async_set_context(service_call.context)
                if service_call.service == SERVICE_TURN_ON:
                    await alert.async_turn_on()
                elif service_call.service == SERVICE_TOGGLE:
                    await alert.async_toggle()
                else:
                    await alert.async_turn_off()

    # Setup service calls
    hass.services.async_register(
        DOMAIN,
        SERVICE_TURN_OFF,
        async_handle_alert_service,
        schema=ALERT_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_alert_service, schema=ALERT_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, async_handle_alert_service, schema=ALERT_SERVICE_SCHEMA
    )

    for alert in entities:
        alert.async_write_ha_state()

    return True


class Alert(ToggleEntity):
    """Representation of an alert."""

    def __init__(
        self,
        hass,
        entity_id,
        name,
        watched_entity_id,
        state,
        repeat,
        skip_first,
        message_template,
        done_message_template,
        notifiers,
        can_ack,
        title_template,
        data,
    ):
        """Initialize the alert."""
        self.hass = hass
        self._name = name
        self._alert_state = state
        self._skip_first = skip_first
        self._data = data

        self._message_template = message_template
        if self._message_template is not None:
            self._message_template.hass = hass

        self._done_message_template = done_message_template
        if self._done_message_template is not None:
            self._done_message_template.hass = hass

        self._title_template = title_template
        if self._title_template is not None:
            self._title_template.hass = hass

        self._notifiers = notifiers
        self._can_ack = can_ack

        self._delay = [timedelta(minutes=val) for val in repeat]
        self._next_delay = 0

        self._firing = False
        self._ack = False
        self._cancel = None
        self._send_done_message = False
        self.entity_id = f"{DOMAIN}.{entity_id}"

        event.async_track_state_change(
            hass, watched_entity_id, self.watched_entity_change
        )

    @property
    def name(self):
        """Return the name of the alert."""
        return self._name

    @property
    def should_poll(self):
        """Home Assistant need not poll these entities."""
        return False

    @property
    def state(self):
        """Return the alert status."""
        if self._firing:
            if self._ack:
                return STATE_OFF
            return STATE_ON
        return STATE_IDLE

    @property
    def hidden(self):
        """Hide the alert when it is not firing."""
        return not self._can_ack or not self._firing

    async def watched_entity_change(self, entity, from_state, to_state):
        """Determine if the alert should start or stop."""
        _LOGGER.debug("Watched entity (%s) has changed", entity)
        if to_state.state == self._alert_state and not self._firing:
            await self.begin_alerting()
        if to_state.state != self._alert_state and self._firing:
            await self.end_alerting()

    async def begin_alerting(self):
        """Begin the alert procedures."""
        _LOGGER.debug("Beginning Alert: %s", self._name)
        self._ack = False
        self._firing = True
        self._next_delay = 0

        if not self._skip_first:
            await self._notify()
        else:
            await self._schedule_notify()

        self.async_write_ha_state()

    async def end_alerting(self):
        """End the alert procedures."""
        _LOGGER.debug("Ending Alert: %s", self._name)
        self._cancel()
        self._ack = False
        self._firing = False
        if self._send_done_message:
            await self._notify_done_message()
        self.async_write_ha_state()

    async def _schedule_notify(self):
        """Schedule a notification."""
        delay = self._delay[self._next_delay]
        next_msg = now() + delay
        self._cancel = event.async_track_point_in_time(
            self.hass, self._notify, next_msg
        )
        self._next_delay = min(self._next_delay + 1, len(self._delay) - 1)

    async def _notify(self, *args):
        """Send the alert notification."""
        if not self._firing:
            return

        if not self._ack:
            _LOGGER.info("Alerting: %s", self._name)
            self._send_done_message = True

            if self._message_template is not None:
                message = self._message_template.async_render()
            else:
                message = self._name

            await self._send_notification_message(message)
        await self._schedule_notify()

    async def _notify_done_message(self, *args):
        """Send notification of complete alert."""
        _LOGGER.info("Alerting: %s", self._done_message_template)
        self._send_done_message = False

        if self._done_message_template is None:
            return

        message = self._done_message_template.async_render()

        await self._send_notification_message(message)

    async def _send_notification_message(self, message):

        msg_payload = {ATTR_MESSAGE: message}

        if self._title_template is not None:
            title = self._title_template.async_render()
            msg_payload.update({ATTR_TITLE: title})
        if self._data:
            msg_payload.update({ATTR_DATA: self._data})

        _LOGGER.debug(msg_payload)

        for target in self._notifiers:
            await self.hass.services.async_call(DOMAIN_NOTIFY, target, msg_payload)

    async def async_turn_on(self, **kwargs):
        """Async Unacknowledge alert."""
        _LOGGER.debug("Reset Alert: %s", self._name)
        self._ack = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Async Acknowledge alert."""
        _LOGGER.debug("Acknowledged Alert: %s", self._name)
        self._ack = True
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs):
        """Async toggle alert."""
        if self._ack:
            return await self.async_turn_on()
        return await self.async_turn_off()
