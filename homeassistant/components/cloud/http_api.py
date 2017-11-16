"""The HTTP api to control the cloud integration."""
import asyncio
from functools import wraps
import logging

import voluptuous as vol
import async_timeout

from homeassistant.components.http import (
    HomeAssistantView, RequestDataValidator)

from . import auth_api
from .const import DOMAIN, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass):
    """Initialize the HTTP api."""
    hass.http.register_view(CloudLoginView)
    hass.http.register_view(CloudLogoutView)
    hass.http.register_view(CloudAccountView)
    hass.http.register_view(CloudRegisterView)
    hass.http.register_view(CloudConfirmRegisterView)
    hass.http.register_view(CloudForgotPasswordView)
    hass.http.register_view(CloudConfirmForgotPasswordView)


_CLOUD_ERRORS = {
    auth_api.UserNotFound: (400, "User does not exist."),
    auth_api.UserNotConfirmed: (400, 'Email not confirmed.'),
    auth_api.Unauthenticated: (401, 'Authentication failed.'),
    auth_api.PasswordChangeRequired: (400, 'Password change required.'),
    auth_api.ExpiredCode: (400, 'Confirmation code has expired.'),
    auth_api.InvalidCode: (400, 'Invalid confirmation code.'),
    asyncio.TimeoutError: (502, 'Unable to reach the Home Assistant cloud.')
}


def _handle_cloud_errors(handler):
    """Helper method to handle auth errors."""
    @asyncio.coroutine
    @wraps(handler)
    def error_handler(view, request, *args, **kwargs):
        """Handle exceptions that raise from the wrapped request handler."""
        try:
            result = yield from handler(view, request, *args, **kwargs)
            return result

        except (auth_api.CloudError, asyncio.TimeoutError) as err:
            err_info = _CLOUD_ERRORS.get(err.__class__)
            if err_info is None:
                err_info = (502, 'Unexpected error: {}'.format(err))
            status, msg = err_info
            return view.json_message(msg, status_code=status,
                                     message_code=err.__class__.__name__)

    return error_handler


class CloudLoginView(HomeAssistantView):
    """Login to Home Assistant cloud."""

    url = '/api/cloud/login'
    name = 'api:cloud:login'

    @asyncio.coroutine
    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('email'): str,
        vol.Required('password'): str,
    }))
    def post(self, request, data):
        """Handle login request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            yield from hass.async_add_job(auth_api.login, cloud, data['email'],
                                          data['password'])

        hass.async_add_job(cloud.iot.connect)
        # Allow cloud to start connecting.
        yield from asyncio.sleep(0, loop=hass.loop)
        return self.json(_account_data(cloud))


class CloudLogoutView(HomeAssistantView):
    """Log out of the Home Assistant cloud."""

    url = '/api/cloud/logout'
    name = 'api:cloud:logout'

    @asyncio.coroutine
    @_handle_cloud_errors
    def post(self, request):
        """Handle logout request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            yield from cloud.logout()

        return self.json_message('ok')


class CloudAccountView(HomeAssistantView):
    """View to retrieve account info."""

    url = '/api/cloud/account'
    name = 'api:cloud:account'

    @asyncio.coroutine
    def get(self, request):
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

    @asyncio.coroutine
    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('email'): str,
        vol.Required('password'): vol.All(str, vol.Length(min=6)),
    }))
    def post(self, request, data):
        """Handle registration request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            yield from hass.async_add_job(
                auth_api.register, cloud, data['email'], data['password'])

        return self.json_message('ok')


class CloudConfirmRegisterView(HomeAssistantView):
    """Confirm registration on the Home Assistant cloud."""

    url = '/api/cloud/confirm_register'
    name = 'api:cloud:confirm_register'

    @asyncio.coroutine
    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('confirmation_code'): str,
        vol.Required('email'): str,
    }))
    def post(self, request, data):
        """Handle registration confirmation request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            yield from hass.async_add_job(
                auth_api.confirm_register, cloud, data['confirmation_code'],
                data['email'])

        return self.json_message('ok')


class CloudForgotPasswordView(HomeAssistantView):
    """View to start Forgot Password flow.."""

    url = '/api/cloud/forgot_password'
    name = 'api:cloud:forgot_password'

    @asyncio.coroutine
    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('email'): str,
    }))
    def post(self, request, data):
        """Handle forgot password request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            yield from hass.async_add_job(
                auth_api.forgot_password, cloud, data['email'])

        return self.json_message('ok')


class CloudConfirmForgotPasswordView(HomeAssistantView):
    """View to finish Forgot Password flow.."""

    url = '/api/cloud/confirm_forgot_password'
    name = 'api:cloud:confirm_forgot_password'

    @asyncio.coroutine
    @_handle_cloud_errors
    @RequestDataValidator(vol.Schema({
        vol.Required('confirmation_code'): str,
        vol.Required('email'): str,
        vol.Required('new_password'): vol.All(str, vol.Length(min=6))
    }))
    def post(self, request, data):
        """Handle forgot password confirm request."""
        hass = request.app['hass']
        cloud = hass.data[DOMAIN]

        with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
            yield from hass.async_add_job(
                auth_api.confirm_forgot_password, cloud,
                data['confirmation_code'], data['email'],
                data['new_password'])

        return self.json_message('ok')


def _account_data(cloud):
    """Generate the auth data JSON response."""
    claims = cloud.claims

    return {
        'email': claims['email'],
        'sub_exp': claims.get('custom:sub-exp'),
        'cloud': cloud.iot.state,
    }
