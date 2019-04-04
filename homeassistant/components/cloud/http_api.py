"""The HTTP api to control the cloud integration."""
import asyncio
from functools import wraps
import logging

import attr
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

from .const import (
    DOMAIN, REQUEST_TIMEOUT, PREF_ENABLE_ALEXA, PREF_ENABLE_GOOGLE,
    PREF_GOOGLE_ALLOW_UNLOCK, InvalidTrustedNetworks)

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


_CLOUD_ERRORS = {
    InvalidTrustedNetworks:
        (500, 'Remote UI not compatible with 127.0.0.1/::1'
              ' as a trusted network.')
}


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
    hass.components.websocket_api.async_register_command(
        websocket_remote_connect)
    hass.components.websocket_api.async_register_command(
        websocket_remote_disconnect)
    hass.http.register_view(GoogleActionsSyncView)
    hass.http.register_view(CloudLoginView)
    hass.http.register_view(CloudLogoutView)
    hass.http.register_view(CloudRegisterView)
    hass.http.register_view(CloudResendConfirmView)
    hass.http.register_view(CloudForgotPasswordView)

    from hass_nabucasa import auth

    _CLOUD_ERRORS.update({
        auth.UserNotFound:
            (400, "User does not exist."),
        auth.UserNotConfirmed:
            (400, 'Email not confirmed.'),
        auth.Unauthenticated:
            (401, 'Authentication failed.'),
        auth.PasswordChangeRequired:
            (400, 'Password change required.'),
        asyncio.TimeoutError:
            (502, 'Unable to reach the Home Assistant cloud.'),
        aiohttp.ClientError:
            (500, 'Error making internal request'),
    })


def _handle_cloud_errors(handler):
    """Webview decorator to handle auth errors."""
    @wraps(handler)
    async def error_handler(view, request, *args, **kwargs):
        """Handle exceptions that raise from the wrapped request handler."""
        try:
            result = await handler(view, request, *args, **kwargs)
            return result

        except Exception as err:  # pylint: disable=broad-except
            status, msg = _process_cloud_exception(err, request.path)
            return view.json_message(
                msg, status_code=status,
                message_code=err.__class__.__name__.lower())

    return error_handler


def _ws_handle_cloud_errors(handler):
    """Websocket decorator to handle auth errors."""
    @wraps(handler)
    async def error_handler(hass, connection, msg):
        """Handle exceptions that raise from the wrapped handler."""
        try:
            return await handler(hass, connection, msg)

        except Exception as err:  # pylint: disable=broad-except
            err_status, err_msg = _process_cloud_exception(err, msg['type'])
            connection.send_error(msg['id'], err_status, err_msg)

    return error_handler


def _process_cloud_exception(exc, where):
    """Process a cloud exception."""
    err_info = _CLOUD_ERRORS.get(exc.__class__)
    if err_info is None:
        _LOGGER.exception(
            "Unexpected error processing request for %s", where)
        err_info = (502, 'Unexpected error: {}'.format(exc))
    return err_info


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
            await hass.async_add_job(cloud.auth.check_token)

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
            await hass.async_add_job(cloud.auth.login, data['email'],
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
                cloud.auth.register, data['email'], data['password'])

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
                cloud.auth.resend_email_confirm, data['email'])

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
                cloud.auth.forgot_password, data['email'])

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


@_require_cloud_login
@websocket_api.async_response
async def websocket_subscription(hass, connection, msg):
    """Handle request for account info."""
    from hass_nabucasa.const import STATE_DISCONNECTED
    cloud = hass.data[DOMAIN]

    with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
        response = await cloud.fetch_subscription_info()

    if response.status != 200:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'request_failed', 'Failed to request subscription'))

    data = await response.json()

    # Check if a user is subscribed but local info is outdated
    # In that case, let's refresh and reconnect
    if data.get('provider') and not cloud.is_connected:
        _LOGGER.debug(
            "Found disconnected account with valid subscriotion, connecting")
        await hass.async_add_executor_job(cloud.auth.renew_access_token)

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
    await cloud.client.prefs.async_update(**changes)

    connection.send_message(websocket_api.result_message(msg['id']))


@_require_cloud_login
@websocket_api.async_response
@_ws_handle_cloud_errors
async def websocket_hook_create(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]
    hook = await cloud.cloudhooks.async_create(msg['webhook_id'], False)
    connection.send_message(websocket_api.result_message(msg['id'], hook))


@_require_cloud_login
@websocket_api.async_response
@_ws_handle_cloud_errors
async def websocket_hook_delete(hass, connection, msg):
    """Handle request for account info."""
    cloud = hass.data[DOMAIN]
    await cloud.cloudhooks.async_delete(msg['webhook_id'])
    connection.send_message(websocket_api.result_message(msg['id']))


def _account_data(cloud):
    """Generate the auth data JSON response."""
    from hass_nabucasa.const import STATE_DISCONNECTED

    if not cloud.is_logged_in:
        return {
            'logged_in': False,
            'cloud': STATE_DISCONNECTED,
        }

    claims = cloud.claims
    client = cloud.client
    remote = cloud.remote

    # Load remote certificate
    if remote.certificate:
        certificate = attr.asdict(remote.certificate)
    else:
        certificate = None

    return {
        'logged_in': True,
        'email': claims['email'],
        'cloud': cloud.iot.state,
        'prefs': client.prefs.as_dict(),
        'google_entities': client.google_user_config['filter'].config,
        'google_domains': list(google_sh.DOMAIN_TO_GOOGLE_TYPES),
        'alexa_entities': client.alexa_config.should_expose.config,
        'alexa_domains': list(alexa_sh.ENTITY_ADAPTERS),
        'remote_domain': remote.instance_domain,
        'remote_connected': remote.is_connected,
        'remote_certificate': certificate,
    }


@_require_cloud_login
@websocket_api.async_response
@_ws_handle_cloud_errors
@websocket_api.websocket_command({
    'type': 'cloud/remote/connect'
})
async def websocket_remote_connect(hass, connection, msg):
    """Handle request for connect remote."""
    cloud = hass.data[DOMAIN]
    await cloud.client.prefs.async_update(remote_enabled=True)
    await cloud.remote.connect()
    connection.send_result(msg['id'], _account_data(cloud))


@_require_cloud_login
@websocket_api.async_response
@_ws_handle_cloud_errors
@websocket_api.websocket_command({
    'type': 'cloud/remote/disconnect'
})
async def websocket_remote_disconnect(hass, connection, msg):
    """Handle request for disconnect remote."""
    cloud = hass.data[DOMAIN]
    await cloud.client.prefs.async_update(remote_enabled=False)
    await cloud.remote.disconnect()
    connection.send_result(msg['id'], _account_data(cloud))
