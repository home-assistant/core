"""Support for Google Actions Smart Home Control."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any
from uuid import uuid4

from aiohttp import ClientError, ClientResponseError
from aiohttp.web import Request, Response
import jwt

from homeassistant.components import webhook
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import STORAGE_DIR, Store
from homeassistant.util import dt as dt_util, json as json_util

from .const import (
    CONF_CLIENT_EMAIL,
    CONF_ENTITY_CONFIG,
    CONF_EXPOSE,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    CONF_PRIVATE_KEY,
    CONF_REPORT_STATE,
    CONF_SECURE_DEVICES_PIN,
    CONF_SERVICE_ACCOUNT,
    DOMAIN,
    GOOGLE_ASSISTANT_API_ENDPOINT,
    HOMEGRAPH_SCOPE,
    HOMEGRAPH_TOKEN_URL,
    REPORT_STATE_BASE_URL,
    REQUEST_SYNC_BASE_URL,
    SOURCE_CLOUD,
    STORE_AGENT_USER_IDS,
    STORE_GOOGLE_LOCAL_WEBHOOK_ID,
)
from .helpers import AbstractConfig
from .smart_home import async_handle_message

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
    return jwt.encode(jwt_raw, key, algorithm="RS256")


async def _get_homegraph_token(
    hass: HomeAssistant, jwt_signed: str
) -> dict[str, Any] | list[Any] | Any:
    headers = {
        "Authorization": f"Bearer {jwt_signed}",
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

    _store: GoogleConfigStore

    def __init__(self, hass, config):
        """Initialize the config."""
        super().__init__(hass)
        self._config = config
        self._access_token = None
        self._access_token_renew = None

    async def async_initialize(self):
        """Perform async initialization of config."""
        # We need to initialize the store before calling super
        self._store = GoogleConfigStore(self.hass)
        await self._store.async_initialize()

        await super().async_initialize()

        self.async_enable_local_sdk()

    @property
    def enabled(self):
        """Return if Google is enabled."""
        return True

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
        return self._config.get(CONF_REPORT_STATE)

    def get_local_user_id(self, webhook_id):
        """Map webhook ID to a Home Assistant user ID.

        Any action initiated by Google Assistant via the local SDK will be attributed
        to the returned user ID.

        Return None if no user id is found for the webhook_id.
        """
        # Note: The manually setup Google Assistant currently returns the Google agent
        # user ID instead of a valid Home Assistant user ID
        found_agent_user_id = None
        for agent_user_id, agent_user_data in self._store.agent_user_ids.items():
            if agent_user_data[STORE_GOOGLE_LOCAL_WEBHOOK_ID] == webhook_id:
                found_agent_user_id = agent_user_id
                break

        return found_agent_user_id

    def get_local_webhook_id(self, agent_user_id):
        """Return the webhook ID to be used for actions for a given agent user id via the local SDK."""
        if data := self._store.agent_user_ids.get(agent_user_id):
            return data[STORE_GOOGLE_LOCAL_WEBHOOK_ID]
        return None

    def get_agent_user_id_from_context(self, context):
        """Get agent user ID making request."""
        return context.user_id

    def get_agent_user_id_from_webhook(self, webhook_id):
        """Map webhook ID to a Google agent user ID.

        Return None if no agent user id is found for the webhook_id.
        """
        for agent_user_id, agent_user_data in self._store.agent_user_ids.items():
            if agent_user_data[STORE_GOOGLE_LOCAL_WEBHOOK_ID] == webhook_id:
                return agent_user_id

        return None

    def should_expose(self, state) -> bool:
        """Return if entity should be exposed."""
        expose_by_default = self._config.get(CONF_EXPOSE_BY_DEFAULT)
        exposed_domains = self._config.get(CONF_EXPOSED_DOMAINS)

        if state.attributes.get("view") is not None:
            # Ignore entities that are views
            return False

        if state.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            return False

        entity_registry = er.async_get(self.hass)
        registry_entry = entity_registry.async_get(state.entity_id)
        if registry_entry:
            auxiliary_entity = (
                registry_entry.entity_category is not None
                or registry_entry.hidden_by is not None
            )
        else:
            auxiliary_entity = False

        explicit_expose = self.entity_config.get(state.entity_id, {}).get(CONF_EXPOSE)

        domain_exposed_by_default = (
            expose_by_default and state.domain in exposed_domains
        )

        # Expose an entity by default if the entity's domain is exposed by default
        # and the entity is not a config or diagnostic entity
        entity_exposed_by_default = domain_exposed_by_default and not auxiliary_entity

        # Expose an entity if the entity's is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        is_default_exposed = entity_exposed_by_default and explicit_expose is not False

        return is_default_exposed or explicit_expose

    def should_2fa(self, state):
        """If an entity should have 2FA checked."""
        return True

    async def _async_request_sync_devices(self, agent_user_id: str) -> HTTPStatus:
        if CONF_SERVICE_ACCOUNT in self._config:
            return await self.async_call_homegraph_api(
                REQUEST_SYNC_BASE_URL, {"agentUserId": agent_user_id}
            )

        _LOGGER.error("No configuration for request_sync available")
        return HTTPStatus.INTERNAL_SERVER_ERROR

    async def async_connect_agent_user(self, agent_user_id: str):
        """Add a synced and known agent_user_id.

        Called before sending a sync response to Google.
        """
        self._store.add_agent_user_id(agent_user_id)

    async def async_disconnect_agent_user(self, agent_user_id: str):
        """Turn off report state and disable further state reporting.

        Called when:
         - The user disconnects their account from Google.
         - When the cloud configuration is initialized
         - When sync entities fails with 404
        """
        self._store.pop_agent_user_id(agent_user_id)

    @callback
    def async_get_agent_users(self):
        """Return known agent users."""
        return self._store.agent_user_ids

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
        """Call a homegraph api with authentication."""
        session = async_get_clientsession(self.hass)

        async def _call():
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "X-GFE-SSL": "yes",
            }
            async with session.post(url, headers=headers, json=data) as res:
                _LOGGER.debug(
                    "Response on %s with data %s was %s", url, data, await res.text()
                )
                res.raise_for_status()
                return res.status

        try:
            await self._async_update_token()
            try:
                return await _call()
            except ClientResponseError as error:
                if error.status == HTTPStatus.UNAUTHORIZED:
                    _LOGGER.warning(
                        "Request for %s unauthorized, renewing token and retrying", url
                    )
                    await self._async_update_token(True)
                    return await _call()
                raise
        except ClientResponseError as error:
            _LOGGER.error("Request for %s failed: %d", url, error.status)
            return error.status
        except (TimeoutError, ClientError):
            _LOGGER.error("Could not contact %s", url)
            return HTTPStatus.INTERNAL_SERVER_ERROR

    async def async_report_state(
        self, message: dict[str, Any], agent_user_id: str, event_id: str | None = None
    ) -> HTTPStatus:
        """Send a state report to Google."""
        data = {
            "requestId": uuid4().hex,
            "agentUserId": agent_user_id,
            "payload": message,
        }
        if event_id is not None:
            data["eventId"] = event_id
        return await self.async_call_homegraph_api(REPORT_STATE_BASE_URL, data)


class GoogleConfigStore:
    """A configuration store for google assistant."""

    _STORAGE_VERSION = 1
    _STORAGE_VERSION_MINOR = 2
    _STORAGE_KEY = DOMAIN
    _data: dict[str, Any]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a configuration store."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass,
            self._STORAGE_VERSION,
            self._STORAGE_KEY,
            minor_version=self._STORAGE_VERSION_MINOR,
        )

    async def async_initialize(self) -> None:
        """Finish initializing the ConfigStore."""
        should_save_data = False
        if (data := await self._store.async_load()) is None:
            # if the store is not found create an empty one
            # Note that the first request is always a cloud request,
            # and that will store the correct agent user id to be used for local requests
            data = {
                STORE_AGENT_USER_IDS: {},
            }
            should_save_data = True

        for agent_user_id, agent_user_data in data[STORE_AGENT_USER_IDS].items():
            if STORE_GOOGLE_LOCAL_WEBHOOK_ID not in agent_user_data:
                data[STORE_AGENT_USER_IDS][agent_user_id] = {
                    **agent_user_data,
                    STORE_GOOGLE_LOCAL_WEBHOOK_ID: webhook.async_generate_id(),
                }
                should_save_data = True

        if should_save_data:
            await self._store.async_save(data)

        self._data = data

    @property
    def agent_user_ids(self) -> dict[str, Any]:
        """Return a list of connected agent user_ids."""
        return self._data[STORE_AGENT_USER_IDS]

    @callback
    def add_agent_user_id(self, agent_user_id: str) -> None:
        """Add an agent user id to store."""
        if agent_user_id not in self._data[STORE_AGENT_USER_IDS]:
            self._data[STORE_AGENT_USER_IDS][agent_user_id] = {
                STORE_GOOGLE_LOCAL_WEBHOOK_ID: webhook.async_generate_id(),
            }
            self._store.async_delay_save(lambda: self._data, 1.0)

    @callback
    def pop_agent_user_id(self, agent_user_id: str) -> None:
        """Remove agent user id from store."""
        if agent_user_id in self._data[STORE_AGENT_USER_IDS]:
            self._data[STORE_AGENT_USER_IDS].pop(agent_user_id, None)
            self._store.async_delay_save(lambda: self._data, 1.0)


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
            request.app[KEY_HASS],
            self.config,
            request["hass_user"].id,
            request["hass_user"].id,
            message,
            SOURCE_CLOUD,
        )
        return self.json(result)


async def async_get_users(hass: HomeAssistant) -> list[str]:
    """Return stored users.

    This is called by the cloud integration to import from the previously shared store.
    """
    path = hass.config.path(STORAGE_DIR, GoogleConfigStore._STORAGE_KEY)  # noqa: SLF001
    try:
        store_data = await hass.async_add_executor_job(json_util.load_json, path)
    except HomeAssistantError:
        return []

    if (
        not isinstance(store_data, dict)
        or not (data := store_data.get("data"))
        or not isinstance(data, dict)
        or not (agent_user_ids := data.get("agent_user_ids"))
        or not isinstance(agent_user_ids, dict)
    ):
        return []
    return list(agent_user_ids)
