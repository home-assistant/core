"""Config flow for Somfy."""
import asyncio
import logging

import async_timeout

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from .const import CLIENT_ID, CLIENT_SECRET, DOMAIN

AUTH_CALLBACK_PATH = '/auth/somfy/callback'
AUTH_CALLBACK_NAME = 'auth:somfy:callback'

_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, client_id, client_secret):
    """Register a flow implementation.
    client_id: Client id.
    client_secret: Client secret.
    """
    hass.data[DOMAIN][CLIENT_ID] = client_id
    hass.data[DOMAIN][CLIENT_SECRET] = client_secret


@config_entries.HANDLERS.register('somfy')
class SomfyFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, user_input=None):
        """Handle external yaml configuration."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')
        return await self.async_step_auth()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if DOMAIN not in self.hass.data:
            return self.async_abort(reason='no_flows')

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        return await self.async_step_auth()

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='external_setup')

        errors = {}

        if user_input is not None:
            errors['base'] = 'follow_link'

        try:
            with async_timeout.timeout(10):
                url = await self._get_authorization_url()
        except asyncio.TimeoutError:
            return self.async_abort(reason='authorize_url_timeout')
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason='authorize_url_fail')

        return self.async_show_form(
            step_id='auth',
            description_placeholders={'authorization_url': url},
            errors=errors,
        )

    async def _get_authorization_url(self):
        """Get Somfy authorization url."""
        from pymfy.api.somfy_api import SomfyApi
        client_id = self.hass.data[DOMAIN][CLIENT_ID]
        client_secret = self.hass.data[DOMAIN][CLIENT_SECRET]
        redirect_uri = '{}{}'.format(
            self.hass.config.api.base_url, AUTH_CALLBACK_PATH)
        api = SomfyApi(client_id, client_secret, redirect_uri)

        self.hass.http.register_view(SomfyAuthCallbackView())
        return await self.hass.async_add_executor_job(
            api.get_authorization_url)

    async def async_step_code(self, code=None):
        """Received code for authentication."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        if code is None:
            return self.async_abort(reason='no_code')

        _LOGGER.debug("Should close all flows below %s",
                      self.hass.config_entries.flow.async_progress())

        return await self._async_create_session(code)

    async def _async_create_session(self, code):
        """Create Somfy api and entries."""
        client_id = self.hass.data[DOMAIN][CLIENT_ID]
        client_secret = self.hass.data[DOMAIN][CLIENT_SECRET]
        from pymfy.api.somfy_api import SomfyApi
        redirect_uri = '{}{}'.format(
            self.hass.config.api.base_url, AUTH_CALLBACK_PATH)
        api = SomfyApi(client_id, client_secret, redirect_uri)
        token = await self.hass.async_add_executor_job(api.request_token, None,
                                                       code)
        _LOGGER.debug("Got new token")
        _LOGGER.info('Successfully authenticated Somfy')
        return self.async_create_entry(
            title='',
            data={
                'token': token,
                'refresh_args': {
                    'client_id': client_id,
                    'client_secret': client_secret
                }
            },
        )


class SomfyAuthCallbackView(HomeAssistantView):
    """Somfy Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    @staticmethod
    async def get(request):
        """Receive authorization code."""
        from aiohttp import web
        hass = request.app['hass']
        if 'code' in request.query:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={'source': 'code'},
                    data=request.query['code'],
                ))
        return web.HTTPFound('/')
