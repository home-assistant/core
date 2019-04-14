"""Config flow to configure Logi Circle component."""
import asyncio
from collections import OrderedDict

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_SENSORS
from homeassistant.core import callback

from .const import (
    CONF_API_KEY, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_REDIRECT_URI,
    DEFAULT_CACHEDB, DOMAIN)

_TIMEOUT = 15  # seconds

DATA_FLOW_IMPL = 'logi_circle_flow_implementation'
EXTERNAL_ERRORS = 'logi_errors'
AUTH_CALLBACK_PATH = '/api/logi_circle'
AUTH_CALLBACK_NAME = 'api:logi_circle'


@callback
def register_flow_implementation(hass, domain, client_id, client_secret,
                                 api_key, redirect_uri, sensors):
    """Register a flow implementation.

    domain: Domain of the component responsible for the implementation.
    client_id: Client ID.
    client_secret: Client secret.
    api_key: API key issued by Logitech.
    redirect_uri: Auth callback redirect URI.
    sensors: Sensor config.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL][domain] = {
        CONF_CLIENT_ID: client_id,
        CONF_CLIENT_SECRET: client_secret,
        CONF_API_KEY: api_key,
        CONF_REDIRECT_URI: redirect_uri,
        CONF_SENSORS: sensors,
        EXTERNAL_ERRORS: None
    }


@config_entries.HANDLERS.register(DOMAIN)
class LogiCircleFlowHandler(config_entries.ConfigFlow):
    """Config flow for Logi Circle component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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

        external_error = (self.hass.data[DATA_FLOW_IMPL][DOMAIN]
                          [EXTERNAL_ERRORS])
        errors = {}
        if external_error:
            # Handle error from another flow
            errors['base'] = external_error
            self.hass.data[DATA_FLOW_IMPL][DOMAIN][EXTERNAL_ERRORS] = None
        elif user_input is not None:
            errors['base'] = 'follow_link'

        url = self._get_authorization_url()

        return self.async_show_form(
            step_id='auth',
            description_placeholders={'authorization_url': url},
            errors=errors)

    def _get_authorization_url(self):
        """Create temporary Circle session and generate authorization url."""
        from logi_circle import LogiCircle
        flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]
        client_id = flow[CONF_CLIENT_ID]
        client_secret = flow[CONF_CLIENT_SECRET]
        api_key = flow[CONF_API_KEY]
        redirect_uri = flow[CONF_REDIRECT_URI]

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

        return await self._async_create_session(code)

    async def _async_create_session(self, code):
        """Create Logi Circle session and entries."""
        from logi_circle import LogiCircle
        from logi_circle.exception import AuthorizationFailed

        flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        client_id = flow[CONF_CLIENT_ID]
        client_secret = flow[CONF_CLIENT_SECRET]
        api_key = flow[CONF_API_KEY]
        redirect_uri = flow[CONF_REDIRECT_URI]
        sensors = flow[CONF_SENSORS]

        logi_session = LogiCircle(
            client_id=client_id,
            client_secret=client_secret,
            api_key=api_key,
            redirect_uri=redirect_uri,
            cache_file=DEFAULT_CACHEDB)

        try:
            with async_timeout.timeout(_TIMEOUT, loop=self.hass.loop):
                await logi_session.authorize(code)
        except AuthorizationFailed:
            (self.hass.data[DATA_FLOW_IMPL][DOMAIN]
             [EXTERNAL_ERRORS]) = 'auth_error'
            return self.async_abort(reason='external_error')
        except asyncio.TimeoutError:
            (self.hass.data[DATA_FLOW_IMPL][DOMAIN]
             [EXTERNAL_ERRORS]) = 'auth_timeout'
            return self.async_abort(reason='external_error')

        account_id = (await logi_session.account)['accountId']
        await logi_session.close()
        return self.async_create_entry(
            title='Logi Circle ({})'.format(account_id),
            data={
                CONF_CLIENT_ID: client_id,
                CONF_CLIENT_SECRET: client_secret,
                CONF_API_KEY: api_key,
                CONF_REDIRECT_URI: redirect_uri,
                CONF_SENSORS: sensors})


class LogiCircleAuthCallbackView(HomeAssistantView):
    """Logi Circle Authorization Callback View."""

    requires_auth = False
    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME

    async def get(self, request):
        """Receive authorization code."""
        hass = request.app['hass']
        if 'code' in request.query:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={'source': 'code'},
                    data=request.query['code'],
                ))
            return self.json_message("Authorisation code saved")
        return self.json_message("Authorisation code missing "
                                 "from query string", status_code=400)
