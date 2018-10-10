"""Local Nest authentication."""
import time
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN

MONZO_AUTH_CALLBACK_PATH = '/api/monzo/callback'
MONZO_AUTH_CALLBACK_NAME = 'api:monzo'

ATTR_CLIENT_ID = 'client_id'
ATTR_CLIENT_SECRET = 'client_secret'
ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'
ATTR_LAST_SAVED_AT = 'last_saved_at'

_LOGGER = logging.getLogger(__name__)


class MonzoAuthCallbackView(HomeAssistantView):
    """Monzo Authorization Callback View."""

    requires_auth = False
    url = MONZO_AUTH_CALLBACK_PATH
    name = MONZO_AUTH_CALLBACK_NAME

    def __init__(self, async_step_import, oauth):
        """Initialize."""
        self.async_step_import = async_step_import
        self.oauth = oauth

    @callback
    def get(self, request):
        """Receive authorization token."""
        from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
        from oauthlib.oauth2.rfc6749.errors import MissingTokenError

        hass = request.app['hass']
        data = request.query

        response_message = """Monzo has been successfully authorized!
        You can close this window now!"""

        result = None
        if data.get('code') is not None:
            redirect_uri = '{}{}'.format(
                hass.config.api.base_url, MONZO_AUTH_CALLBACK_PATH)

            try:
                result = self.oauth.fetch_access_token(data.get('code'),
                                                       redirect_uri)
            except MissingTokenError as error:
                _LOGGER.error("Missing token: %s", error)
                response_message = """Something went wrong when
                attempting authenticating with Monzo. The error
                encountered was {}. Please try again!""".format(error)
            except MismatchingStateError as error:
                _LOGGER.error("Mismatched state, CSRF error: %s", error)
                response_message = """Something went wrong when
                attempting authenticating with Monzo. The error
                encountered was {}. Please try again!""".format(error)
        else:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Monzo.
                An unknown error occurred. Please try again!
                """

        if result is None:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Monzo.
                An unknown error occurred. Please try again!
                """

        html_response = """<html><head><title>Monzo Auth</title></head>
        <body><h1>{}</h1></body></html>""".format(response_message)

        if result:
            tokens = {
                ATTR_CLIENT_ID: self.oauth.client_id,
                ATTR_CLIENT_SECRET: self.oauth.client_secret,
                ATTR_ACCESS_TOKEN: result.get('access_token'),
                ATTR_REFRESH_TOKEN: result.get('refresh_token'),
                ATTR_LAST_SAVED_AT: int(time.time())
            }

        hass.async_add_job(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data={
                'client_id': self.oauth.client_id,
                'client_secret': self.oauth.client_secret,
                'tokens': tokens
            }))

        return html_response
