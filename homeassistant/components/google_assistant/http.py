"""Support for Google Actions Smart Home Control."""
from datetime import timedelta
import logging
import jwt
from uuid import uuid4

from aiohttp.web import Request, Response

# Typing imports
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    GOOGLE_ASSISTANT_API_ENDPOINT,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    CONF_ENTITY_CONFIG,
    CONF_EXPOSE,
    CONF_REPORT_STATE,
    CONF_SECURE_DEVICES_PIN,
    CONF_SERVICE_ACCOUNT,
    CONF_CLIENT_EMAIL,
    CONF_PRIVATE_KEY,
    HOMEGRAPH_AUDIENCE,
    HOMEGRAPH_SCOPE,
    REPORT_STATE_BASE_URL,
)
from .smart_home import async_handle_message
from .helpers import AbstractConfig

_LOGGER = logging.getLogger(__name__)


class GoogleConfig(AbstractConfig):
    """Config for manual setup of Google."""

    def __init__(self, hass, config):
        """Initialize the config."""
        super().__init__(hass)
        self._config = config

    @property
    def enabled(self):
        """Return if Google is enabled."""
        return True

    @property
    def agent_user_id(self):
        """Return Agent User Id to use for query responses."""
        return self._config.get("agent_user_id")

    @property
    def entity_config(self):
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @property
    def secure_devices_pin(self):
        """Return entity config."""
        return self._config.get(CONF_SECURE_DEVICES_PIN)

    @property
    def should_report_state(self):
        """Return if states should be proactively reported."""
        # pylint: disable=no-self-use
        return self._config.get(CONF_REPORT_STATE)

    def should_expose(self, state) -> bool:
        """Return if entity should be exposed."""
        expose_by_default = self._config.get(CONF_EXPOSE_BY_DEFAULT)
        exposed_domains = self._config.get(CONF_EXPOSED_DOMAINS)

        if state.attributes.get("view") is not None:
            # Ignore entities that are views
            return False

        if state.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        explicit_expose = self.entity_config.get(state.entity_id, {}).get(CONF_EXPOSE)

        domain_exposed_by_default = (
            expose_by_default and state.domain in exposed_domains
        )

        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        is_default_exposed = domain_exposed_by_default and explicit_expose is not False

        return is_default_exposed or explicit_expose

    def should_2fa(self, state):
        """If an entity should have 2FA checked."""
        return True

    def _async_get_jwt(self):
        now = dt_util.utcnow()

        if CONF_SERVICE_ACCOUNT not in self._config:
            raise Exception("No service account defined in config")

        jwt_raw = {
            "iss": self._config[CONF_SERVICE_ACCOUNT][CONF_CLIENT_EMAIL],
            "scope": HOMEGRAPH_SCOPE,
            "aud": HOMEGRAPH_AUDIENCE,
            "ist": now.timestamp(),
            "exp": (now + timedelta(hours=1)).timestamp(),
        }
        private_key = self._config[CONF_SERVICE_ACCOUNT][CONF_PRIVATE_KEY]
        return jwt.encode(jwt_raw, private_key).decode("utf-8")

    async def _async_get_access_token(self):

        jwt_signed = self._async_get_jwt()
        headers = {"Authorization": "Bearer {}".format(jwt_signed)}

        session = async_get_clientsession(self.hass)
        async with session.post(HOMEGRAPH_AUDIENCE, headers=headers) as res:
            res.raise_for_status()
            return res.text()

    async def async_report_state(self, message):
        """Send a state report to Google."""
        access_token = await self._async_get_access_token()

        headers = {
            "Authorization": "Bearer {}".format(access_token),
            "X-GFE-SSL": "yes",
        }

        data = {
            "requestId": uuid4().hex,
            "agentUserId": self.agent_user_id,
            "payload": message,
        }

        session = async_get_clientsession(self.hass)
        async with session.post(
            REPORT_STATE_BASE_URL, headers=headers, json=data
        ) as res:
            res.raise_for_status()


@callback
def async_register_http(hass, cfg):
    """Register HTTP views for Google Assistant."""
    hass.http.register_view(GoogleAssistantView(GoogleConfig(hass, cfg)))


class GoogleAssistantView(HomeAssistantView):
    """Handle Google Assistant requests."""

    url = GOOGLE_ASSISTANT_API_ENDPOINT
    name = "api:google_assistant"
    requires_auth = True

    def __init__(self, config):
        """Initialize the Google Assistant request handler."""
        self.config = config

    async def post(self, request: Request) -> Response:
        """Handle Google Assistant requests."""
        message: dict = await request.json()
        result = await async_handle_message(
            request.app["hass"], self.config, request["hass_user"].id, message
        )
        return self.json(result)
