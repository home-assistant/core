"""Auth component utils."""
from functools import wraps

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant


def validate_current_user(
        only_owner=False, only_system_user=False, allow_system_user=True,
        only_active_user=True, only_inactive_user=False):
    """Decorator that will validate login user exist in current WS connection.

    Will write out error message if not authenticated.
    """
    def validator(func):
        """Decorator be called."""
        @wraps(func)
        def check_current_user(hass: HomeAssistant,
                               connection: websocket_api.ActiveConnection,
                               msg):
            """Check current user."""
            def output_error(message_id, message):
                """Output error message."""
                connection.send_message_outside(websocket_api.error_message(
                    msg['id'], message_id, message))

            if connection.user is None:
                output_error('no_user', 'Not authenticated as a user')
                return

            if only_owner and not connection.user.is_owner:
                output_error('only_owner', 'Only allowed as owner')
                return

            if (only_system_user and
                    not connection.user.system_generated):
                output_error('only_system_user',
                             'Only allowed as system user')
                return

            if (not allow_system_user
                    and connection.user.system_generated):
                output_error('not_system_user', 'Not allowed as system user')
                return

            if (only_active_user and
                    not connection.user.is_active):
                output_error('only_active_user',
                             'Only allowed as active user')
                return

            if only_inactive_user and connection.user.is_active:
                output_error('only_inactive_user',
                             'Not allowed as active user')
                return

            return func(hass, connection, msg)

        return check_current_user

    return validator
