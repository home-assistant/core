"""The HTTP api to control the cloud integration."""
import asyncio
from functools import wraps
import logging

import async_timeout
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import (
    RequestDataValidator)
from homeassistant.components import websocket_api

from . import auth_api
from .const import DOMAIN, REQUEST_TIMEOUT
from .iot import STATE_DISCONNECTED, STATE_CONNECTED

_LOGGER = logging.getLogger(__name__)


WS_TYPE_STATUS = 'cloud/status'
SCHEMA_WS_STATUS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_STATUS,
})


WS_TYPE_UPDATE_PREFS = 'cloud/update_prefs'
SCHEMA_WS_UPDATE_PREFS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_UPDATE_PREFS,
    vol.Optional('google_enabled'): bool,
    vol.Optional('alexa_enabled'): bool,
})


WS_TYPE_SUBSCRIPTION = 'cloud/subscription'
SCHEMA_WS_SUBSCRIPTION = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_SUBSCRIPTION,
})


async def async_setup(hass):
    """Initialize the HTTP API."""
    hass.components.websocket_api.async_register_command(
        WS_TYPE_STATUS, websocket_cloud_status,
        SCHEMA_WS_STATUS
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SUBSCRIPTION, websocket_subscription,
        SCHEMA_WS_SUBSCRIPTION
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE_PREFS, websocket_update_prefs,
        SCHEMA_WS_UPDATE_PREFS
    )
    hass.http.register_view(GoogleActionsSyncView)
    hass.http.register_view(CloudLoginView)
    hass.http.register_view(CloudLogoutView)
    hass.http.register_view(CloudRegisterView)
    hass.http.register_view(CloudResendConfirmView)
    hass.http.register_view(CloudForgotPasswordView)


_CLOUD_ERRORS = {
    auth_api.UserNotFound: (400, "User does not exist."),
    auth_api.UserNotConfirmed: (400, 'Email not confirmed.'),
    auth_api.Unauthenticated: (401, 'Authentication failed.'),
    auth_api.PasswordChangeRequired: (400, 'Password change required.'),
    asyncio.TimeoutError: (502, 'Unable to reach the Home Assistant cloud.')
}


def _handle_cloud_errors(handler):
    """Handle auth errors."""
    @wraps(handler)
    async def error_handler(view, request, *args, **kwargs):
        """Handle exceptions that raise from the wrapped request handler."""
        try:
            result = await handler(view, request, *args, **kwargs)
            return result

        except (auth_api.CloudError, asyncio.TimeoutError) as err:
            err_info = _CLOUD_ERRORS.get(err.__class__)
            if err_info is None:
                err_info = (502, 'Unexpected error: {}'.format(err))
            status, msg = err_info
            return view.json_message(msg, status_code=status,
                                     message_code=err.__class__.__name__)

    return error_handler


class GoogleActionsSyncView(HomeAssistantView):
    """Trigger a Google Actions Smart Home Sync."""

    url = '/api/cloud/google_actions/sync'
    name = 'api:cloud:google_actions/sync'

    @_handle_cloud_errors
    async def post(self, request):
        """Trigger a Google Actions sync."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]
        websession = hass.helpers.aiohttp_client.async_get_clientsession()

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            await hass.async_add_job(auth_api.check_token, cloud)

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            req = await websession.post(
                cloud.google_actions_sync_url, headers={
                    'authorization': cloud.id_token
                })

        return self.json({}, status_code=req.status)


class CloudLoginView(HomeAssistantView):
    """Login to Home Assistant cloud."""

    url = '/api/cloud/login'
    name = 'api:cloud:login'

    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('email'): str,
        vol.Required('password'): str,
    }))
    async def post(self, request, data):
        """Handle login request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            await hass.async_add_job(auth_api.login, cloud, data['email'],
                                     data['password'])

        hass.async_add_job(cloud.iot.connect)
        return self.json({'success': True})


class CloudLogoutView(HomeAssistantView):
    """Log out of the Home Assistant cloud."""

    url = '/api/cloud/logout'
    name = 'api:cloud:logout'

    @_handle_cloud_errors
    async def post(self, request):
        """Handle logout request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            await cloud.logout()

        return self.json_message('ok')


class CloudRegisterView(HomeAssistantView):
    """Register on the Home Assistant cloud."""

    url = '/api/cloud/register'
    name = 'api:cloud:register'

    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('email'): str,
        vol.Required('password'): vol.All(str, vol.Length(min=6)),
    }))
    async def post(self, request, data):
        """Handle registration request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            await hass.async_add_job(
                auth_api.register, cloud, data['email'], data['password'])

        return self.json_message('ok')


class CloudResendConfirmView(HomeAssistantView):
    """Resend email confirmation code."""

    url = '/api/cloud/resend_confirm'
    name = 'api:cloud:resend_confirm'

    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('email'): str,
    }))
    async def post(self, request, data):
        """Handle resending confirm email code request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            await hass.async_add_job(
                auth_api.resend_email_confirm, cloud, data['email'])

        return self.json_message('ok')


class CloudForgotPasswordView(HomeAssistantView):
    """View to start Forgot Password flow.."""

    url = '/api/cloud/forgot_password'
    name = 'api:cloud:forgot_password'

    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('email'): str,
    }))
    async def post(self, request, data):
        """Handle forgot password request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            await hass.async_add_job(
                auth_api.forgot_password, cloud, data['email'])

        return self.json_message('ok')


@callback
def websocket_cloud_status(hass, connection, msg):
    """Handle request for account info.

    Async friendly.
    """
    cloud = hass.data[DOMAIN]
    connection.send_message(
        websocket_api.result_message(msg['id'], _account_data(cloud)))


@websocket_api.async_response
async def websocket_subscription(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]

    if not cloud.is_logged_in:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'not_logged_in',
            'You need to be logged in to the cloud.'))
        return

    with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
        response = await cloud.fetch_subscription_info()

    if response.status != 200:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'request_failed', 'Failed to request subscription'))

    data = await response.json()

    # Check if a user is subscribed but local info is outdated
    # In that case, let's refresh and reconnect
    if data.get('provider') and cloud.iot.state != STATE_CONNECTED:
        _LOGGER.debug(
            "Found disconnected account with valid subscriotion, connecting")
        await hass.async_add_executor_job(
            auth_api.renew_access_token, cloud)

        # Cancel reconnect in progress
        if cloud.iot.state != STATE_DISCONNECTED:
            await cloud.iot.disconnect()

        hass.async_create_task(cloud.iot.connect())

    connection.send_message(websocket_api.result_message(msg['id'], data))


@websocket_api.async_response
async def websocket_update_prefs(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]

    if not cloud.is_logged_in:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'not_logged_in',
            'You need to be logged in to the cloud.'))
        return

    changes = dict(msg)
    changes.pop('id')
    changes.pop('type')
    await cloud.update_preferences(**changes)

    connection.send_message(websocket_api.result_message(
        msg['id'], {'success': True}))


def _account_data(cloud):
    """Generate the auth data JSON response."""
    if not cloud.is_logged_in:
        return {
            'logged_in': False,
            'cloud': STATE_DISCONNECTED,
        }

    claims = cloud.claims

    return {
        'logged_in': True,
        'email': claims['email'],
        'cloud': cloud.iot.state,
        'google_enabled': cloud.google_enabled,
        'alexa_enabled': cloud.alexa_enabled,
    }
