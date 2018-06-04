"""Google Assistant OAuth View."""

import logging

# Typing imports
# pylint: disable=using-constant-test,unused-import,ungrouped-imports
# if False:
from aiohttp.web import Request, Response  # NOQA
from typing import Dict, Any  # NOQA

from homeassistant.core import HomeAssistant  # NOQA
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    HTTP_BAD_REQUEST,
    HTTP_UNAUTHORIZED,
    HTTP_MOVED_PERMANENTLY,
)

from .const import (
    GOOGLE_ASSISTANT_API_ENDPOINT,
    CONF_PROJECT_ID, CONF_CLIENT_ID, CONF_ACCESS_TOKEN
)

BASE_OAUTH_URL = 'https://oauth-redirect.googleusercontent.com'
REDIRECT_TEMPLATE_URL = \
    '{}/r/{}#access_token={}&token_type=bearer&state={}'

_LOGGER = logging.getLogger(__name__)


class GoogleAssistantAuthView(HomeAssistantView):
    """Handle Google Actions auth requests."""

    url = GOOGLE_ASSISTANT_API_ENDPOINT + '/auth'
    name = 'api:google_assistant:auth'
    requires_auth = False

    def __init__(self, hass: HomeAssistant, cfg: Dict[str, Any]) -> None:
        """Initialize instance of the view."""
        super().__init__()

        self.project_id = cfg.get(CONF_PROJECT_ID)
        self.client_id = cfg.get(CONF_CLIENT_ID)
        self.access_token = cfg.get(CONF_ACCESS_TOKEN)

    async def get(self, request: Request) -> Response:
        """Handle oauth token request."""
        query = request.query
        redirect_uri = query.get('redirect_uri')
        if not redirect_uri:
            msg = 'missing redirect_uri field'
            _LOGGER.warning(msg)
            return self.json_message(msg, status_code=HTTP_BAD_REQUEST)

        if self.project_id not in redirect_uri:
            msg = 'missing project_id in redirect_uri'
            _LOGGER.warning(msg)
            return self.json_message(msg, status_code=HTTP_BAD_REQUEST)

        state = query.get('state')
        if not state:
            msg = 'oauth request missing state'
            _LOGGER.warning(msg)
            return self.json_message(msg, status_code=HTTP_BAD_REQUEST)

        client_id = query.get('client_id')
        if self.client_id != client_id:
            msg = 'invalid client id'
            _LOGGER.warning(msg)
            return self.json_message(msg, status_code=HTTP_UNAUTHORIZED)

        generated_url = redirect_url(self.project_id, self.access_token, state)

        _LOGGER.info('user login in from Google Assistant')
        return self.json_message(
            'redirect success',
            status_code=HTTP_MOVED_PERMANENTLY,
            headers={'Location': generated_url})


def redirect_url(project_id: str, access_token: str, state: str) -> str:
    """Generate the redirect format for the oauth request."""
    return REDIRECT_TEMPLATE_URL.format(BASE_OAUTH_URL, project_id,
                                        access_token, state)
