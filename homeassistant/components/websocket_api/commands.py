"""Commands part of Websocket API."""
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.const import (
    MATCH_ALL, EVENT_TIME_CHANGED, EVENT_STATE_CHANGED)
from homeassistant.core import callback, DOMAIN as HASS_DOMAIN
from homeassistant.exceptions import Unauthorized, ServiceNotFound, \
    HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_get_all_descriptions

from . import const, decorators, messages


@callback
def async_register_commands(hass, async_reg):
    """Register commands."""
    async_reg(hass, handle_subscribe_events)
    async_reg(hass, handle_unsubscribe_events)
    async_reg(hass, handle_call_service)
    async_reg(hass, handle_get_states)
    async_reg(hass, handle_get_services)
    async_reg(hass, handle_get_config)
    async_reg(hass, handle_ping)


def pong_message(iden):
    """Return a pong message."""
    return {
        'id': iden,
        'type': 'pong',
    }


@callback
@decorators.websocket_command({
    vol.Required('type'): 'subscribe_events',
    vol.Optional('event_type', default=MATCH_ALL): str,
})
def handle_subscribe_events(hass, connection, msg):
    """Handle subscribe events command.

    Async friendly.
    """
    from .permissions import SUBSCRIBE_WHITELIST

    event_type = msg['event_type']

    if (event_type not in SUBSCRIBE_WHITELIST and
            not connection.user.is_admin):
        raise Unauthorized

    if event_type == EVENT_STATE_CHANGED:
        @callback
        def forward_events(event):
            """Forward state changed events to websocket."""
            if not connection.user.permissions.check_entity(
                    event.data['entity_id'], POLICY_READ):
                return

            connection.send_message(messages.event_message(msg['id'], event))

    else:
        @callback
        def forward_events(event):
            """Forward events to websocket."""
            if event.event_type == EVENT_TIME_CHANGED:
                return

            connection.send_message(messages.event_message(
                msg['id'], event.as_dict()
            ))

    connection.subscriptions[msg['id']] = hass.bus.async_listen(
        event_type, forward_events)

    connection.send_message(messages.result_message(msg['id']))


@callback
@decorators.websocket_command({
    vol.Required('type'): 'unsubscribe_events',
    vol.Required('subscription'): cv.positive_int,
})
def handle_unsubscribe_events(hass, connection, msg):
    """Handle unsubscribe events command.

    Async friendly.
    """
    subscription = msg['subscription']

    if subscription in connection.subscriptions:
        connection.subscriptions.pop(subscription)()
        connection.send_message(messages.result_message(msg['id']))
    else:
        connection.send_message(messages.error_message(
            msg['id'], const.ERR_NOT_FOUND, 'Subscription not found.'))


@decorators.async_response
@decorators.websocket_command({
    vol.Required('type'): 'call_service',
    vol.Required('domain'): str,
    vol.Required('service'): str,
    vol.Optional('service_data'): dict
})
async def handle_call_service(hass, connection, msg):
    """Handle call service command.

    Async friendly.
    """
    blocking = True
    if (msg['domain'] == HASS_DOMAIN and
            msg['service'] in ['restart', 'stop']):
        blocking = False

    try:
        await hass.services.async_call(
            msg['domain'], msg['service'], msg.get('service_data'), blocking,
            connection.context(msg))
        connection.send_message(messages.result_message(msg['id']))
    except ServiceNotFound:
        connection.send_message(messages.error_message(
            msg['id'], const.ERR_NOT_FOUND, 'Service not found.'))
    except HomeAssistantError as err:
        connection.logger.exception(err)
        connection.send_message(messages.error_message(
            msg['id'], const.ERR_HOME_ASSISTANT_ERROR, '{}'.format(err)))
    except Exception as err:  # pylint: disable=broad-except
        connection.logger.exception(err)
        connection.send_message(messages.error_message(
            msg['id'], const.ERR_UNKNOWN_ERROR, '{}'.format(err)))


@callback
@decorators.websocket_command({
    vol.Required('type'): 'get_states',
})
def handle_get_states(hass, connection, msg):
    """Handle get states command.

    Async friendly.
    """
    entity_perm = connection.user.permissions.check_entity
    states = [
        state for state in hass.states.async_all()
        if entity_perm(state.entity_id, 'read')
    ]

    connection.send_message(messages.result_message(
        msg['id'], states))


@decorators.async_response
@decorators.websocket_command({
    vol.Required('type'): 'get_services',
})
async def handle_get_services(hass, connection, msg):
    """Handle get services command.

    Async friendly.
    """
    descriptions = await async_get_all_descriptions(hass)
    connection.send_message(
        messages.result_message(msg['id'], descriptions))


@callback
@decorators.websocket_command({
    vol.Required('type'): 'get_config',
})
def handle_get_config(hass, connection, msg):
    """Handle get config command.

    Async friendly.
    """
    connection.send_message(messages.result_message(
        msg['id'], hass.config.as_dict()))


@callback
@decorators.websocket_command({
    vol.Required('type'): 'ping',
})
def handle_ping(hass, connection, msg):
    """Handle ping command.

    Async friendly.
    """
    connection.send_message(pong_message(msg['id']))
