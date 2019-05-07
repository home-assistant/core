"""Config flow for Withings."""
from collections import OrderedDict
import logging
from typing import Optional

import nokia
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.util import slugify

from . import const

DATA_FLOW_IMPL = 'withings_flow_implementation'

_LOGGER = logging.getLogger(__name__)


def auth_callback_path(profile: str) -> str:
    """Create an auth callback path."""
    return '{}/{}'.format(const.AUTH_CALLBACK_PATH, slugify(profile))


def auth_callback_name(profile: str) -> str:
    """Create an auth callback name."""
    return '{}:{}'.format(const.AUTH_CALLBACK_NAME, slugify(profile))


@callback
def register_flow_implementation(
        hass,
        client_id,
        client_secret,
        base_url,
        profile
):
    """Register a flow implementation.

    domain: Domain of the component responsible for the implementation.
    name: Name of the component.
    client_id: Client id.
    client_secret: Client secret.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL][profile] = {
        const.CLIENT_ID: client_id,
        const.CLIENT_SECRET: client_secret,
        const.BASE_URL: base_url,
        const.PROFILE: profile,
    }


@config_entries.HANDLERS.register(const.DOMAIN)
class WithingsFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize flow."""
        self.flow_profile = None

    def async_profile_config_entry(
            self,
            profile: str
    ) -> Optional[ConfigEntry]:
        """Get a profile config entry."""
        entries = self.hass.config_entries.async_entries(const.DOMAIN)
        for entry in entries:
            if entry.title == profile:
                return entry

        return None

    def get_auth_client(self, profile: str):
        """Get a new auth client."""
        flow = self.hass.data[DATA_FLOW_IMPL][profile]
        client_id = flow[const.CLIENT_ID]
        client_secret = flow[const.CLIENT_SECRET]
        base_url = flow[const.BASE_URL].rstrip('/')
        callback_path = auth_callback_path(profile).lstrip('/')
        auth_callback_path_str = const.AUTH_CALLBACK_PATH.lstrip('/')

        # Clean up the base url in case the user configured a bit too much.
        if base_url.endswith(callback_path):
            base_url = base_url[:-len(callback_path)]
        if base_url.endswith(auth_callback_path_str):
            base_url = base_url[:-len(auth_callback_path_str)]

        callback_uri = '{}/{}'.format(
            base_url.rstrip('/'),
            callback_path.lstrip('/')
        )

        return nokia.NokiaAuth(
            client_id,
            client_secret,
            callback_uri,
            scope=','.join(['user.info', 'user.metrics', 'user.activity'])
        )

    async def async_step_user(self, user_input=None):
        """Create an entry for selecting a profile."""
        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if not flows:
            _LOGGER.debug("no flows")
            return self.async_abort(reason='no_flows')

        if user_input and const.PROFILE in user_input:
            return await self.async_step_auth(user_input)

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required('profile'):
                    vol.In(list(flows))
            }))

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        if user_input and const.CODE in user_input:
            return await self.async_step_code(user_input)

        errors = {}

        if user_input is not None:
            errors['base'] = 'follow_link'

        profile = user_input[const.PROFILE]

        auth_client = self.get_auth_client(profile)

        self.hass.http.register_view(WithingsAuthCallbackView(
            self.flow_id,
            profile
        ))

        url = auth_client.get_authorize_url()

        return self.async_show_form(
            step_id='auth',
            description_placeholders={
                'authorization_url': url,
                'profile': profile,
            },
            errors=errors,
        )

    async def async_step_code(self, user_input=None):
        """Received code for authentication."""
        # if self.hass.config_entries.async_entries(const.DOMAIN):
        #     return self.async_abort(reason='already_setup')

        if user_input is None:
            return self.async_abort(reason='api_no_data')

        if const.PROFILE not in user_input or not user_input[const.PROFILE]:
            return self.async_abort(reason='api_no_profile_data')

        if const.CODE not in user_input or not user_input[const.CODE]:
            return self.async_abort(reason='api_no_code_data')

        _LOGGER.debug("Should close all flows below %s",
                      self.hass.config_entries.flow.async_progress())
        # Remove notification if no other discovery config entries in progress

        profile = user_input[const.PROFILE]
        code = user_input[const.CODE]

        return await self._async_create_session(profile, code)

    async def _async_create_session(self, profile, code):
        """Create withings session and entries."""
        auth_client = self.get_auth_client(profile)

        _LOGGER.debug('Requesting credentials with code: %s.', code)
        credentials = auth_client.get_credentials(code)

        return self.async_create_entry(
            title=profile,
            data={
                const.PROFILE: profile,
                const.CREDENTIALS: credentials.__dict__,
            }
        )


class WithingsAuthCallbackView(HomeAssistantView):
    """Withings Authorization Callback View."""

    requires_auth = False

    def __init__(self, flow_id: str, profile: str):
        """Constructor."""
        self._profile = profile
        self._flow_id = flow_id
        self._url = auth_callback_path(profile)
        self._name = auth_callback_name(profile)

    @property
    def profile(self):
        """Return profile."""
        return self._profile

    @property
    def flow_id(self):
        """Return flow id."""
        return self._flow_id

    @property
    def url(self):
        """Return url."""
        return self._url

    @property
    def name(self):
        """Return name."""
        return self._name

    @callback
    def get(self, request):
        """Receive authorization code."""
        hass = request.app['hass']
        if 'code' in request.query:
            hass.async_create_task(
                hass.config_entries.flow.async_configure(
                    self.flow_id,
                    {
                        const.PROFILE: self.profile,
                        const.CODE: request.query['code'],
                    }
                )
            )

        return "OK!"
