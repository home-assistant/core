"""Config flow to configure the OpenUV component."""

import os

from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.util.json import load_json

from .local_auth import MonzoAuthCallbackView
from .const import DOMAIN

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

MONZO_AUTH_START = '/api/monzo'
MONZO_AUTH_CALLBACK_PATH = '/api/monzo/callback'


@callback
def configured_instances(hass):
    """Return a set of configured Monzo instances."""
    return set(
        '{0}'.format(
            entry.data[CONF_CLIENT_ID]
            for entry in hass.config_entries.async_entries(DOMAIN)))


@config_entries.HANDLERS.register(DOMAIN)
class MonzoFlowHandler(config_entries.ConfigFlow):
    """Handle an Monzo config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        pass

    async def async_step_init(self, user_input=None):
        """Handle the start of the config flow."""
        errors = {}

        if user_input is not None:
            client_id = user_input.get(CONF_CLIENT_ID, None)
            client_secret = user_input.get(CONF_CLIENT_SECRET, None)
            if None not in (client_id, client_secret):
                if client_id in configured_instances(self.hass):
                    errors['base'] = 'identifier_exists'
                else:
                    return await self._set_up_redirect(user_input)

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_CLIENT_ID)] = str
        data_schema[vol.Required(CONF_CLIENT_SECRET)] = str

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Monzo account.

        Route the user to a website to authenticate with Monzo. Depending on
        implementation type we expect a pin or an external component to
        deliver the authentication code.
        """
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        errors = {}
        monzo_auth_start_redirect = '{}{}'.format(
            self.hass.config.api.base_url,
            MONZO_AUTH_START)

        return self.async_show_form(
            step_id='link',
            description_placeholders={
                'url': monzo_auth_start_redirect
            },
            errors=errors,
        )

    async def _set_up_redirect(self, user_input=None):
        from monzo import MonzoOAuth2Client

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        if user_input is not None:
            client_id = user_input.get(CONF_CLIENT_ID, None)
            client_secret = user_input.get(CONF_CLIENT_SECRET, None)
            redirect_uri = '{}{}'.format(self.hass.config.api.base_url,
                                         MONZO_AUTH_CALLBACK_PATH)

            oauth = MonzoOAuth2Client(client_id=client_id,
                                      client_secret=client_secret,
                                      redirect_uri=redirect_uri)

            monzo_auth_start_url, _ = oauth.authorize_token_url()

            self.hass.http.register_redirect(MONZO_AUTH_START,
                                             monzo_auth_start_url)
            self.hass.http.register_view(MonzoAuthCallbackView(
                self.async_step_import, oauth))

        return await self.async_step_link(user_input)

    async def async_step_import(self, info):
        """Import existing auth from Monzo."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason='already_setup')

        # Create config entry after auth process
        tokens = info.get('tokens', None)
        if tokens is not None:
            return self._entry_from_tokens('Monzo', tokens)

        # Check if component has been initalized without any credentials.
        client_id = info.get(CONF_CLIENT_ID, None)
        client_secret = info.get(CONF_CLIENT_SECRET, None)
        if None in (client_id, client_secret):
            return await self.async_step_init(info)

        # Check if a file to import from exists.
        # If file is empty or missing, start auth process.
        config_path = info['monzo_conf_path']

        if not await self.hass.async_add_job(os.path.isfile, config_path):
            return await self._set_up_redirect(info)

        tokens = await self.hass.async_add_job(load_json, config_path)
        if not tokens:
            return await self._set_up_redirect(info)

        return self._entry_from_tokens(
            'Monzo (import from configuration.yaml)', tokens)

    @callback
    def _entry_from_tokens(self, title, tokens):
        """Create an entry from tokens."""
        return self.async_create_entry(
            title=title,
            data={
                'tokens': tokens
            },
        )
