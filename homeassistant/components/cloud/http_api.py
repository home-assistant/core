"""The HTTP api to control the cloud integration."""
import asyncio
from functools import wraps
import logging

import async_timeout
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import (
    RequestDataValidator)

from . import auth_api
from .const import DOMAIN, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass):
    """Initialize the HTTP API."""
    hass.http.register_view(GoogleActionsSyncView)
    hass.http.register_view(CloudLoginView)
    hass.http.register_view(CloudLogoutView)
    hass.http.register_view(CloudAccountView)
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
        # Allow cloud to start connecting.
        await asyncio.sleep(0, loop=hass.loop)
        return self.json(_account_data(cloud))


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


class CloudAccountView(HomeAssistantView):
    """View to retrieve account info."""

    url = '/api/cloud/account'
    name = 'api:cloud:account'

    async def get(self, request):
        """Get account info."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        if not cloud.is_logged_in:
            return self.json_message('Not logged in', 400)

        return self.json(_account_data(cloud))


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


def _account_data(cloud):
    """Generate the auth data JSON response."""
    claims = cloud.claims

    return {
        'email': claims['email'],
        'sub_exp': claims['custom:sub-exp'],
        'cloud': cloud.iot.state,
    }
