"""Support for Google Actions Smart Home Control."""
import asyncio
from datetime import timedelta
import logging
from uuid import uuid4
import jwt

from aiohttp import ClientResponseError, ClientError
from aiohttp.web import Request, Response

# Typing imports
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback, ServiceCall
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    GOOGLE_ASSISTANT_API_ENDPOINT,
    CONF_API_KEY,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    CONF_ENTITY_CONFIG,
    CONF_EXPOSE,
    CONF_REPORT_STATE,
    CONF_SECURE_DEVICES_PIN,
    CONF_SERVICE_ACCOUNT,
    CONF_CLIENT_EMAIL,
    CONF_PRIVATE_KEY,
    DOMAIN,
    HOMEGRAPH_TOKEN_URL,
    HOMEGRAPH_SCOPE,
    REPORT_STATE_BASE_URL,
    REQUEST_SYNC_BASE_URL,
    SERVICE_REQUEST_SYNC,
)
from .smart_home import async_handle_message
from .helpers import AbstractConfig

_LOGGER = logging.getLogger(__name__)


def _get_homegraph_jwt(time, iss, key):
    now = int(time.timestamp())

    jwt_raw = {
        "iss": iss,
        "scope": HOMEGRAPH_SCOPE,
        "aud": HOMEGRAPH_TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(jwt_raw, key, algorithm="RS256").decode("utf-8")


async def _get_homegraph_token(hass, jwt_signed):
    headers = {
        "Authorization": "Bearer {}".format(jwt_signed),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_signed,
    }

    session = async_get_clientsession(hass)
    async with session.post(HOMEGRAPH_TOKEN_URL, headers=headers, data=data) as res:
        res.raise_for_status()
        return await res.json()


class GoogleConfig(AbstractConfig):
    """Config for manual setup of Google."""

    def __init__(self, hass, config):
        """Initialize the config."""
        super().__init__(hass)
        self._config = config
        self._access_token = None
        self._access_token_renew = None

    @property
    def enabled(self):
        """Return if Google is enabled."""
        return True

    @property
    def agent_user_id(self):
        """Return Agent User Id to use for query responses."""
        return None

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

    async def _async_update_token(self, force=False):
        if CONF_SERVICE_ACCOUNT not in self._config:
            _LOGGER.error("Trying to get homegraph api token without service account")
            return

        now = dt_util.utcnow()
        if not self._access_token or now > self._access_token_renew or force:
            token = await _get_homegraph_token(
                self.hass,
                _get_homegraph_jwt(
                    now,
                    self._config[CONF_SERVICE_ACCOUNT][CONF_CLIENT_EMAIL],
                    self._config[CONF_SERVICE_ACCOUNT][CONF_PRIVATE_KEY],
                ),
            )
            self._access_token = token["access_token"]
            self._access_token_renew = now + timedelta(seconds=token["expires_in"])

    async def async_call_homegraph_api(self, url, data):
        """Call a homegraph api with authenticaiton."""
        session = async_get_clientsession(self.hass)

        async def _call():
            headers = {
                "Authorization": "Bearer {}".format(self._access_token),
                "X-GFE-SSL": "yes",
            }
            async with session.post(url, headers=headers, json=data) as res:
                _LOGGER.debug(
                    "Response on %s with data %s was %s", url, data, await res.text()
                )
                res.raise_for_status()

        try:
            await self._async_update_token()
            try:
                await _call()
            except ClientResponseError as error:
                if error.status == 401:
                    _LOGGER.warning(
                        "Request for %s unauthorized, renewing token and retrying", url
                    )
                    await self._async_update_token(True)
                    await _call()
                else:
                    raise
        except ClientResponseError as error:
            _LOGGER.error("Request for %s failed: %d", url, error.status)
        except (asyncio.TimeoutError, ClientError):
            _LOGGER.error("Could not contact %s", url)

    async def async_report_state(self, message):
        """Send a state report to Google."""
        data = {
            "requestId": uuid4().hex,
            "agentUserId": (await self.hass.auth.async_get_owner()).id,
            "payload": message,
        }
        await self.async_call_homegraph_api(REPORT_STATE_BASE_URL, data)


@callback
def async_register_http(hass, cfg):
    """Register HTTP views for Google Assistant."""
    config = GoogleConfig(hass, cfg)
    hass.http.register_view(GoogleAssistantView(config))
    if config.should_report_state:
        config.async_enable_report_state()

    async def request_sync_service_handler(call: ServiceCall):
        """Handle request sync service calls."""
        agent_user_id = call.data.get("agent_user_id") or call.context.user_id

        if agent_user_id is None:
            _LOGGER.warning(
                "No agent_user_id supplied for request_sync. Call as a user or pass in user id as agent_user_id."
            )
            return
        await config.async_call_homegraph_api(
            REQUEST_SYNC_BASE_URL, {"agentUserId": agent_user_id}
        )

    # Register service only if api key is provided
    if CONF_API_KEY not in cfg and CONF_SERVICE_ACCOUNT in cfg:
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST_SYNC, request_sync_service_handler
        )


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
