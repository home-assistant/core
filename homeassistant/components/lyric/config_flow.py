"""Config flow for Honeywell Lyric."""
import asyncio
import logging

import async_timeout
from lyric import Lyric
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigFlow
from .const import (AUTH_CALLBACK_NAME, AUTH_CALLBACK_PATH, DOMAIN,
                    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_LYRIC_CONFIG_FILE)

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
        pass

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id='user',
            # TODO: Secret should be protected in UI
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')

        if user_input is None:
            return await self._show_setup_form(user_input)

        return await self.async_step_auth(user_input)

    async def async_step_auth(self, user_input):
        """Create an entry for auth."""
        # Flow has been triggered from Lyric api
        if isinstance(user_input, str):
            return await self.async_step_code(user_input)

        self.client_id = user_input.get(CONF_CLIENT_ID)
        self.client_secret = user_input.get(CONF_CLIENT_SECRET)

        try:
            with async_timeout.timeout(10):
                url = await self._get_authorization_url(self.client_id,
                                                        self.client_secret)
        except asyncio.TimeoutError:
            return self.async_abort(reason='authorize_url_timeout')

        return self.async_external_step(
            step_id='auth',
            url=url
        )

    async def _get_authorization_url(self, client_id, client_secret):
        """Get Lyric authorization url."""
        redirect_uri = '{}{}'.format(
            self.hass.config.api.base_url, AUTH_CALLBACK_PATH)
        token_cache_file = self.hass.config.path(CONF_LYRIC_CONFIG_FILE)

        lyric = Lyric(app_name='Home Assistant', client_id=client_id,
                      client_secret=client_secret, redirect_uri=redirect_uri,
                      token_cache_file=token_cache_file)

        self.hass.http.register_view(LyricAuthCallbackView())

        url = lyric.getauthorize_url

        return url[:url.find('&state=') + 7] + self.flow_id

    async def async_step_code(self, code):
        """Received code for authentication."""
        return self.async_external_step_done(next_step_id="creation")

    async def async_step_creation(self, user_input):
        """Create Lyric api and entries."""

        client_id = self.client_id
        client_secret = self.client_secret
        token_cache_file = self.hass.config.path(CONF_LYRIC_CONFIG_FILE)

        lyric = Lyric(app_name='Home Assistant', token=user_input,
                      client_id=client_id, client_secret=client_secret,
                      token_cache_file=token_cache_file)

        token = lyric.token

        _LOGGER.info('Successfully authenticated Lyric')

        return self.async_create_entry(
            title='Lyric',
            data={
                'token': token,
                'client_id': client_id,
                'client_secret': client_secret
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
                text="Missing code or state parameter in " + request.url
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
