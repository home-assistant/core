"""The HTTP api to control the cloud integration."""
import asyncio
from functools import wraps
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import (
    RequestDataValidator)
from homeassistant.components import websocket_api
from homeassistant.components.alexa import smart_home as alexa_sh
from homeassistant.components.google_assistant import smart_home as google_sh

from . import auth_api
from .const import (
    DOMAIN, REQUEST_TIMEOUT, PREF_ENABLE_ALEXA, PREF_ENABLE_GOOGLE,
    PREF_GOOGLE_ALLOW_UNLOCK)
from .iot import STATE_DISCONNECTED, STATE_CONNECTED

_LOGGER = logging.getLogger(__name__)


WS_TYPE_STATUS = 'cloud/status'
SCHEMA_WS_STATUS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_STATUS,
})


WS_TYPE_UPDATE_PREFS = 'cloud/update_prefs'
SCHEMA_WS_UPDATE_PREFS = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_UPDATE_PREFS,
    vol.Optional(PREF_ENABLE_GOOGLE): bool,
    vol.Optional(PREF_ENABLE_ALEXA): bool,
    vol.Optional(PREF_GOOGLE_ALLOW_UNLOCK): bool,
})


WS_TYPE_SUBSCRIPTION = 'cloud/subscription'
SCHEMA_WS_SUBSCRIPTION = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_SUBSCRIPTION,
})


WS_TYPE_HOOK_CREATE = 'cloud/cloudhook/create'
SCHEMA_WS_HOOK_CREATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_HOOK_CREATE,
    vol.Required('webhook_id'): str
})


WS_TYPE_HOOK_DELETE = 'cloud/cloudhook/delete'
SCHEMA_WS_HOOK_DELETE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_HOOK_DELETE,
    vol.Required('webhook_id'): str
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
    hass.components.websocket_api.async_register_command(
        WS_TYPE_HOOK_CREATE, websocket_hook_create,
        SCHEMA_WS_HOOK_CREATE
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_HOOK_DELETE, websocket_hook_delete,
        SCHEMA_WS_HOOK_DELETE
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
    """Webview decorator to handle auth errors."""
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


def _require_cloud_login(handler):
    """Websocket decorator that requires cloud to be logged in."""
    @wraps(handler)
    def with_cloud_auth(hass, connection, msg):
        """Require to be logged into the cloud."""
        cloud = hass.data[DOMAIN]
        if not cloud.is_logged_in:
            connection.send_message(websocket_api.error_message(
                msg['id'], 'not_logged_in',
                'You need to be logged in to the cloud.'))
            return

        handler(hass, connection, msg)

    return with_cloud_auth


def _handle_aiohttp_errors(handler):
    """Websocket decorator that handlers aiohttp errors.

    Can only wrap async handlers.
    """
    @wraps(handler)
    async def with_error_handling(hass, connection, msg):
        """Handle aiohttp errors."""
        try:
            await handler(hass, connection, msg)
        except asyncio.TimeoutError:
            connection.send_message(websocket_api.error_message(
                msg['id'], 'timeout', 'Command timed out.'))
        except aiohttp.ClientError:
            connection.send_message(websocket_api.error_message(
                msg['id'], 'unknown', 'Error making request.'))

    return with_error_handling


@_require_cloud_login
@websocket_api.async_response
async def websocket_subscription(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]

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


@_require_cloud_login
@websocket_api.async_response
async def websocket_update_prefs(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]

    changes = dict(msg)
    changes.pop('id')
    changes.pop('type')
    await cloud.prefs.async_update(**changes)

    connection.send_message(websocket_api.result_message(msg['id']))


@_require_cloud_login
@websocket_api.async_response
@_handle_aiohttp_errors
async def websocket_hook_create(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]
    hook = await cloud.cloudhooks.async_create(msg['webhook_id'])
    connection.send_message(websocket_api.result_message(msg['id'], hook))


@_require_cloud_login
@websocket_api.async_response
async def websocket_hook_delete(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]
    await cloud.cloudhooks.async_delete(msg['webhook_id'])
    connection.send_message(websocket_api.result_message(msg['id']))


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
        'prefs': cloud.prefs.as_dict(),
        'google_entities': cloud.google_actions_user_conf['filter'].config,
        'google_domains': list(google_sh.DOMAIN_TO_GOOGLE_TYPES),
        'alexa_entities': cloud.alexa_config.should_expose.config,
        'alexa_domains': list(alexa_sh.ENTITY_ADAPTERS),
    }
