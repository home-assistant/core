"""Commands part of Websocket API."""
import voluptuous as vol

from homeassistant.const import MATCH_ALL, EVENT_TIME_CHANGED
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_get_all_descriptions

from . import const, decorators, messages


TYPE_CALL_SERVICE = 'call_service'
TYPE_EVENT = 'event'
TYPE_GET_CONFIG = 'get_config'
TYPE_GET_SERVICES = 'get_services'
TYPE_GET_STATES = 'get_states'
TYPE_PING = 'ping'
TYPE_PONG = 'pong'
TYPE_SUBSCRIBE_EVENTS = 'subscribe_events'
TYPE_UNSUBSCRIBE_EVENTS = 'unsubscribe_events'


@callback
def async_register_commands(hass):
    """Register commands."""
    async_reg = hass.components.websocket_api.async_register_command
    async_reg(TYPE_SUBSCRIBE_EVENTS, handle_subscribe_events,
              SCHEMA_SUBSCRIBE_EVENTS)
    async_reg(TYPE_UNSUBSCRIBE_EVENTS, handle_unsubscribe_events,
              SCHEMA_UNSUBSCRIBE_EVENTS)
    async_reg(TYPE_CALL_SERVICE, handle_call_service, SCHEMA_CALL_SERVICE)
    async_reg(TYPE_GET_STATES, handle_get_states, SCHEMA_GET_STATES)
    async_reg(TYPE_GET_SERVICES, handle_get_services, SCHEMA_GET_SERVICES)
    async_reg(TYPE_GET_CONFIG, handle_get_config, SCHEMA_GET_CONFIG)
    async_reg(TYPE_PING, handle_ping, SCHEMA_PING)


SCHEMA_SUBSCRIBE_EVENTS = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_SUBSCRIBE_EVENTS,
    vol.Optional('event_type', default=MATCH_ALL): str,
})


SCHEMA_UNSUBSCRIBE_EVENTS = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_UNSUBSCRIBE_EVENTS,
    vol.Required('subscription'): cv.positive_int,
})


SCHEMA_CALL_SERVICE = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_CALL_SERVICE,
    vol.Required('domain'): str,
    vol.Required('service'): str,
    vol.Optional('service_data'): dict
})


SCHEMA_GET_STATES = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_GET_STATES,
})


SCHEMA_GET_SERVICES = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_GET_SERVICES,
})


SCHEMA_GET_CONFIG = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_GET_CONFIG,
})


SCHEMA_PING = messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): TYPE_PING,
})


def event_message(iden, event):
    """Return an event message."""
    return {
        'id': iden,
        'type': TYPE_EVENT,
        'event': event.as_dict(),
    }


def pong_message(iden):
    """Return a pong message."""
    return {
        'id': iden,
        'type': TYPE_PONG,
    }


@callback
def handle_subscribe_events(hass, connection, msg):
    """Handle subscribe events command.

    Async friendly.
    """
    async def forward_events(event):
        """Forward events to websocket."""
        if event.event_type == EVENT_TIME_CHANGED:
            return

        connection.send_message(event_message(msg['id'], event))

    connection.event_listeners[msg['id']] = hass.bus.async_listen(
        msg['event_type'], forward_events)

    connection.send_message(messages.result_message(msg['id']))


@callback
def handle_unsubscribe_events(hass, connection, msg):
    """Handle unsubscribe events command.

    Async friendly.
    """
    subscription = msg['subscription']

    if subscription in connection.event_listeners:
        connection.event_listeners.pop(subscription)()
        connection.send_message(messages.result_message(msg['id']))
    else:
        connection.send_message(messages.error_message(
            msg['id'], const.ERR_NOT_FOUND, 'Subscription not found.'))


@decorators.async_response
async def handle_call_service(hass, connection, msg):
    """Handle call service command.

    Async friendly.
    """
    blocking = True
    if (msg['domain'] == 'homeassistant' and
            msg['service'] in ['restart', 'stop']):
        blocking = False
    await hass.services.async_call(
        msg['domain'], msg['service'], msg.get('service_data'), blocking,
        connection.context(msg))
    connection.send_message(messages.result_message(msg['id']))


@callback
def handle_get_states(hass, connection, msg):
    """Handle get states command.

    Async friendly.
    """
    connection.send_message(messages.result_message(
        msg['id'], hass.states.async_all()))


@decorators.async_response
async def handle_get_services(hass, connection, msg):
    """Handle get services command.

    Async friendly.
    """
    descriptions = await async_get_all_descriptions(hass)
    connection.send_message(
        messages.result_message(msg['id'], descriptions))


@callback
def handle_get_config(hass, connection, msg):
    """Handle get config command.

    Async friendly.
    """
    connection.send_message(messages.result_message(
        msg['id'], hass.config.as_dict()))


@callback
def handle_ping(hass, connection, msg):
    """Handle ping command.

    Async friendly.
    """
    connection.send_message(pong_message(msg['id']))
