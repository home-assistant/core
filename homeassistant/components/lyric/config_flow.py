"""Config flow for Honeywell Lyric."""
import asyncio
import logging

import async_timeout
from lyric import Lyric

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigFlow
from .const import (AUTH_CALLBACK_NAME, AUTH_CALLBACK_PATH, DOMAIN,
                    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LYRIC_CONFIG_FILE,
                    DATA_LYRIC_CONFIG)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class LyricFlowHandler(ConfigFlow):
    """Handle a Lyric config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize Lyric flow."""
        self.client_id = None
        self.client_secret = None
        self.code = None

    async def async_step_user(self, code=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')

        if not self.hass.data.get(DATA_LYRIC_CONFIG):
            return self.async_abort(reason='no_config')

        conf = self.hass.data.get(DATA_LYRIC_CONFIG)

        self.client_id = conf[CONF_CLIENT_ID]
        self.client_secret = conf[CONF_CLIENT_SECRET]

        return await self.async_step_auth(code)

    async def async_step_auth(self, code):
        """Create an entry for auth."""
        # Flow has been triggered from Lyric api
        if code is not None:
            return await self.async_step_code(code)

        try:
            with async_timeout.timeout(10):
                client_id = self.client_id
                client_secret = self.client_secret
                redirect_uri = '{}{}'.format(
                    self.hass.config.api.base_url, AUTH_CALLBACK_PATH)
                token_cache_file = self.hass.config.path(
                    CONF_LYRIC_CONFIG_FILE)

                lyric = Lyric(app_name='Home Assistant', client_id=client_id,
                              client_secret=client_secret,
                              redirect_uri=redirect_uri,
                              token_cache_file=token_cache_file)

                self.hass.http.register_view(LyricAuthCallbackView())

                url = lyric.getauthorize_url

                return self.async_external_step(
                    step_id='auth',
                    url=url[:url.find('&state=') + 7] + self.flow_id)
        except asyncio.TimeoutError:
            return self.async_abort(reason='authorize_url_timeout')

    async def async_step_code(self, code):
        """Received code for authentication."""
        self.code = code
        return self.async_external_step_done(next_step_id="creation")

    async def async_step_creation(self, user_input=None):
        """Create Lyric api and entries."""
        client_id = self.client_id
        client_secret = self.client_secret
        redirect_uri = '{}{}'.format(
            self.hass.config.api.base_url, AUTH_CALLBACK_PATH)
        token_cache_file = self.hass.config.path(CONF_LYRIC_CONFIG_FILE)

        lyric = Lyric(app_name='Home Assistant', client_id=client_id,
                      client_secret=client_secret, redirect_uri=redirect_uri,
                      token_cache_file=token_cache_file)

        # pylint: disable=pointless-statement
        lyric.getauthorize_url
        lyric.authorization_code(self.code, self.flow_id)

        return self.async_create_entry(
            title='Lyric',
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'token': lyric.token
            }
        )


class LyricAuthCallbackView(HomeAssistantView):
    """Lyric Authorization Callback View."""

    requires_auth = False
    name = AUTH_CALLBACK_NAME
    url = AUTH_CALLBACK_PATH

    @staticmethod
    async def get(request):
        """Receive authorization code."""
        from aiohttp import web_response

        if 'code' not in request.query or 'state' not in request.query:
            return web_response.Response(
                text="Missing code or state parameter in %s".format(
                    request.url)
            )

        hass = request.app['hass']
        hass.async_create_task(
            hass.config_entries.flow.async_configure(
                flow_id=request.query['state'],
                user_input=request.query['code']
            ))

        return web_response.Response(
            headers={
                'content-type': 'text/html'
            },
            text="<script>window.close()</script>"
        )
