"""Config flow for Withings."""
from collections import OrderedDict
import logging
from typing import Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify

from . import const

DATA_FLOW_IMPL = 'withings_flow_implementation'

_LOGGER = logging.getLogger(__name__)


def auth_callback_path(profile: str) -> str:
    """Create an auth callback path."""
    return '%s/%s' % (const.AUTH_CALLBACK_PATH, slugify(profile))


def auth_callback_name(profile: str) -> str:
    """Create an auth callback name."""
    return '%s:%s' % (const.AUTH_CALLBACK_NAME, slugify(profile))


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
        import nokia
        flow = self.hass.data[DATA_FLOW_IMPL][profile]
        client_id = flow[const.CLIENT_ID]
        client_secret = flow[const.CLIENT_SECRET]
        base_url = flow[const.BASE_URL]

        callback_uri = '{}{}'.format(
            base_url.rstrip('/'),
            auth_callback_path(profile)
        )

        return nokia.NokiaAuth(
            client_id,
            client_secret,
            callback_uri,
            scope=','.join(['user.info', 'user.metrics', 'user.activity'])
        )

    async def async_step_profile(self, user_input=None):
        """Create an entry for selecting a profile."""
        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if not flows:
            _LOGGER.debug("no flows")
            return self.async_abort(reason='no_flows')

        if user_input is not None and const.PROFILE in user_input:
            return await self.async_step_auth(user_input)

        return self.async_show_form(
            step_id='auth',
            data_schema=vol.Schema({
                vol.Required('profile'):
                    vol.In(list(flows))
            }))

    async def async_step_auth(self, user_input=None):
        """Create an entry for auth."""
        errors = {}

        if user_input is not None:
            errors['base'] = 'follow_link'

        profile = user_input[const.PROFILE]

        auth_client = self.get_auth_client(profile)

        self.hass.http.register_view(WithingsAuthCallbackView(
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

    async def async_step_code(self, data=None):
        """Received code for authentication."""
        # if self.hass.config_entries.async_entries(const.DOMAIN):
        #     return self.async_abort(reason='already_setup')

        if data is None:
            return self.async_abort(reason='api_no_data')

        if const.PROFILE not in data or not data[const.PROFILE]:
            return self.async_abort(reason='api_no_profile_data')

        if const.CODE not in data or not data[const.CODE]:
            return self.async_abort(reason='api_no_code_data')

        _LOGGER.debug("Should close all flows below %s",
                      self.hass.config_entries.flow.async_progress())
        # Remove notification if no other discovery config entries in progress

        profile = data[const.PROFILE]
        code = data[const.CODE]

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
                const.CREDENTIALS: credentials,
            }
        )


class WithingsAuthCallbackView(HomeAssistantView):
    """Withings Authorization Callback View."""

    requires_auth = False

    def __init__(self, profile: str):
        """Constructor."""
        self.profile = profile
        self.url = auth_callback_path(profile)
        self.name = auth_callback_name(profile)

    @callback
    def get(self, request):
        """Receive authorization code."""
        hass = request.app['hass']
        if 'code' in request.query:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    const.DOMAIN,
                    context={'source': const.CODE},
                    data={
                        const.PROFILE: self.profile,
                        const.CODE: request.query['code'],
                    },
                )
            )

        return "OK!"
