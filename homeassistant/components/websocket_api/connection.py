"""Connection session."""
import voluptuous as vol

from homeassistant.core import callback, Context

from . import const, messages


class ActiveConnection:
    """Handle an active websocket client connection."""

    def __init__(self, logger, hass, send_message, user, refresh_token):
        """Initialize an active connection."""
        self.logger = logger
        self.hass = hass
        self.send_message = send_message
        self.user = user
        if refresh_token:
            self.refresh_token_id = refresh_token.id
        else:
            self.refresh_token_id = None

        self.event_listeners = {}
        self.last_id = 0

    def context(self, msg):
        """Return a context."""
        user = self.user
        if user is None:
            return Context()
        return Context(user_id=user.id)

    @callback
    def async_handle(self, msg):
        """Handle a single incoming message."""
        handlers = self.hass.data[const.DOMAIN]

        try:
            msg = messages.MINIMAL_MESSAGE_SCHEMA(msg)
            cur_id = msg['id']
        except vol.Invalid:
            self.logger.error('Received invalid command', msg)
            self.send_message(messages.error_message(
                msg.get('id'), const.ERR_INVALID_FORMAT,
                'Message incorrectly formatted.'))
            return

        if cur_id <= self.last_id:
            self.send_message(messages.error_message(
                cur_id, const.ERR_ID_REUSE,
                'Identifier values have to increase.'))
            return

        if msg['type'] not in handlers:
            self.logger.error(
                'Received invalid command: {}'.format(msg['type']))
            self.send_message(messages.error_message(
                cur_id, const.ERR_UNKNOWN_COMMAND,
                'Unknown command.'))
            return

        handler, schema = handlers[msg['type']]

        try:
            handler(self.hass, self, schema(msg))
        except Exception:  # pylint: disable=broad-except
            self.logger.exception('Error handling message: %s', msg)
            self.send_message(messages.error_message(
                cur_id, const.ERR_UNKNOWN_ERROR,
                'Unknown error.'))

        self.last_id = cur_id

    @callback
    def async_close(self):
        """Close down connection."""
        for unsub in self.event_listeners.values():
            unsub()
