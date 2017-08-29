"""The HTTP api to control the cloud integration."""
import asyncio
import logging

import voluptuous as vol
import async_timeout

from homeassistant.components.http import HomeAssistantView

from . import cloud_api
from .const import DOMAIN, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass):
    """Initialize the HTTP api."""
    hass.http.register_view(CloudLoginView)
    hass.http.register_view(CloudLogoutView)
    hass.http.register_view(CloudAccountView)


class CloudLoginView(HomeAssistantView):
    """Login to Home Assistant cloud."""

    url = '/api/cloud/login'
    name = 'api:cloud:login'
    schema = vol.Schema({
        vol.Required('username'): str,
        vol.Required('password'): str,
    })

    @asyncio.coroutine
    def post(self, request):
        """Validate config and return results."""
        try:
            data = yield from request.json()
        except ValueError:
            _LOGGER.error('Login with invalid JSON')
            return self.json_message('Invalid JSON.', 400)

        try:
            self.schema(data)
        except vol.Invalid as err:
            _LOGGER.error('Login with invalid formatted data')
            return self.json_message(
                'Message format incorrect: {}'.format(err), 400)

        hass = request.app['hass']
        phase = 1
        try:
            with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
                cloud = yield from cloud_api.async_login(
                    hass, data['username'], data['password'])

            phase += 1

            with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
                yield from cloud.async_refresh_account_info()

        except cloud_api.Unauthenticated:
            return self.json_message(
                'Authentication failed (phase {}).'.format(phase), 401)
        except cloud_api.UnknownError:
            return self.json_message(
                'Unknown error occurred (phase {}).'.format(phase), 500)
        except asyncio.TimeoutError:
            return self.json_message(
                'Unable to reach Home Assistant cloud '
                '(phase {}).'.format(phase), 502)

        hass.data[DOMAIN]['cloud'] = cloud
        return self.json(cloud.account)


class CloudLogoutView(HomeAssistantView):
    """Log out of the Home Assistant cloud."""

    url = '/api/cloud/logout'
    name = 'api:cloud:logout'

    @asyncio.coroutine
    def post(self, request):
        """Validate config and return results."""
        hass = request.app['hass']
        try:
            with async_timeout.timeout(REQUEST_TIMEOUT, loop=hass.loop):
                yield from \
                    hass.data[DOMAIN]['cloud'].async_revoke_access_token()

            hass.data[DOMAIN].pop('cloud')

            return self.json({
                'result': 'ok',
            })
        except asyncio.TimeoutError:
            return self.json_message("Could not reach the server.", 502)
        except cloud_api.UnknownError as err:
            return self.json_message(
                "Error communicating with the server ({}).".format(err.status),
                502)


class CloudAccountView(HomeAssistantView):
    """Log out of the Home Assistant cloud."""

    url = '/api/cloud/account'
    name = 'api:cloud:account'

    @asyncio.coroutine
    def get(self, request):
        """Validate config and return results."""
        hass = request.app['hass']

        if 'cloud' not in hass.data[DOMAIN]:
            return self.json_message('Not logged in', 400)

        return self.json(hass.data[DOMAIN]['cloud'].account)
