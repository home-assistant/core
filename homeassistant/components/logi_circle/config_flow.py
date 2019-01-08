"""Config flow to configure Logi Circle component."""
import asyncio
from collections import OrderedDict
import logging

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback

from .const import DOMAIN, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_API_KEY, CONF_REDIRECT_URI
DATA_FLOW_IMPL = 'logi_circle_flow_implementation'
AUTH_CALLBACK_PATH = '/api/logi_circle'
AUTH_CALLBACK_NAME = 'api:logi_circle'

_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, domain, client_id, client_secret, api_key, redirect_uri):
    """Register a flow implementation.

    domain: Domain of the component responsible for the implementation.
    name: Name of the component.
    client_id: Client id.
    client_secret: Client secret.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL][domain] = {
        CONF_CLIENT_ID: client_id,
        CONF_CLIENT_SECRET: client_secret,
        CONF_API_KEY: api_key,
        CONF_REDIRECT_URI: redirect_uri
    }


@config_entries.HANDLERS.register(DOMAIN)
class LogiCircleFlowHandler(config_entries.ConfigFlow):
    """Config flow for Logi Circle component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize flow."""
        self.flow_impl = None

    async def async_step_import(self, user_input=None):
        """Handle external yaml configuration."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        self.flow_impl = DOMAIN

        return await self.async_step_auth()

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        if not flows:
            _LOGGER.debug("no flows")
            return self.async_abort(reason='no_flows')

        if len(flows) == 1:
            self.flow_impl = list(flows)[0]
            return await self.async_step_auth()

        if user_input is not None:
            self.flow_impl = user_input['flow_impl']
            return await self.async_step_auth()

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required('flow_impl'):
                vol.In(list(flows))
            }))

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='external_setup')

        errors = {}

        if user_input is not None:
            errors['base'] = 'follow_link'

        url = self._get_authorization_url()

        return self.async_show_form(
            step_id='auth',
            description_placeholders={'authorization_url': url},
            errors=errors,
        )

    def _get_authorization_url(self):
        """Create temporary Logi Circle session and generate authorization url."""
        from logi_circle import LogiCircle
        flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]
        client_id = flow[CLIENT_ID]
        client_secret = flow[CLIENT_SECRET]
        api_key = flow[API_KEY]
        redirect_uri = flow[REDIRECT_URI]

        logi_session = LogiCircle(
            client_id=client_id,
            client_secret=client_secret,
            api_key=api_key,
            redirect_uri=redirect_uri)

        self.hass.http.register_view(LogiCircleAuthCallbackView())

        return logi_session.authorize_url

    async def async_step_code(self, code=None):
        """Received code for authentication."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        if code is None:
            return self.async_abort(reason='no_code')

        _LOGGER.debug("Should close all flows below %s",
                      self.hass.config_entries.flow.async_progress())
        # Remove notification if no other discovery config entries in progress

        return await self._async_create_session(code)

    async def _async_create_session(self, code):
        """Create point session and entries."""
        from logi_circle import LogiCircle
        flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        client_id = flow[CLIENT_ID]
        client_secret = flow[CLIENT_SECRET]
        api_key = flow[API_KEY]
        redirect_uri = flow[REDIRECT_URI]

        logi_session = LogiCircle(
            client_id=client_id,
            client_secret=client_secret,
            api_key=api_key,
            redirect_uri=redirect_uri)

        await logi_session.authorize(code)

        if not logi_session.authorized:
            _LOGGER.error('Authentication Error')
            return self.async_abort(reason='auth_error')

        _LOGGER.info('Successfully authenticated with Logi Circle API')
        await logi_session.close()

        return self.async_create_entry(
            title='user_email',
            data={
                CONF_CLIENT_ID: client_id,
                CONF_CLIENT_SECRET: client_secret,
                CONF_API_KEY: api_key,
                CONF_REDIRECT_URI: redirect_uri
            }
        )


class LogiCircleAuthCallbackView(HomeAssistantView):
    """Logi Circle Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    @staticmethod
    async def get(request):
        """Receive authorization code."""
        hass = request.app['hass']
        if 'code' in request.query:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={'source': 'code'},
                    data=request.query['code'],
                ))
        return "OK!"
