"""Support for Google Actions Smart Home Control."""

from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any, override
from uuid import uuid4

from aiohttp import ClientError, ClientResponseError
from aiohttp.web import Request, Response
import jwt

from homeassistant.components import webhook
from homeassistant.components.homeassistant.exposed_entities import (
    async_listen_entity_updates,
    async_set_entity_locked,
    async_should_expose,
)
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import MATCH_ALL
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_added_domain
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

EXPOSURE_ATTRIBUTES = {"entity_category", "hidden_by"}


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
        self._should_expose_by_default_cache: dict[tuple[str, bool], bool] = {}

    @override
    async def async_initialize(self):
        """Perform async initialization of config."""
        # We need to initialize the store before calling super
        self._store = GoogleConfigStore(self.hass)
        await self._store.async_initialize()

        await super().async_initialize()

        self._on_deinitialize.append(
            async_listen_entity_updates(
                self.hass, DOMAIN, self.async_schedule_google_sync_all
            )
        )
        self._on_deinitialize.append(
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                self._async_entity_registry_updated,
            )
        )
        self._on_deinitialize.append(
            async_track_state_added_domain(
                self.hass, MATCH_ALL, self._async_state_added
            )
        )

        entity_ids = set(self.hass.states.async_entity_ids())
        entity_ids.update(er.async_get(self.hass).entities)
        entity_ids.update(self.entity_config)
        for entity_id in entity_ids:
            self._async_update_legacy_exposure(entity_id)

        self.async_enable_local_sdk()

    @callback
    def _async_state_added(self, event: Event[EventStateChangedData]) -> None:
        """Push YAML exposure for a newly added entity and schedule a sync.

        This only needs to handle states not registered in entity registry.
        """
        entity_id = event.data["entity_id"]
        entity_registry = er.async_get(self.hass)

        if entity_registry.async_get(entity_id):
            return

        self._async_update_legacy_exposure(entity_id)
        if self.should_expose(entity_id):
            self.async_schedule_google_sync_all()

    @callback
    def _async_entity_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Schedule a sync for an updated or removed entity."""
        entity_id = event.data["entity_id"]

        if event.data["action"] == "remove":
            self.async_schedule_google_sync_all()
            return

        if event.data["action"] == "create":
            self._async_update_legacy_exposure(entity_id)
            if self.should_expose(entity_id):
                self.async_schedule_google_sync_all()
            return

        if event.data["action"] != "update":
            return

        changes = set(event.data["changes"])
        if not changes & (er.ENTITY_DESCRIBING_ATTRIBUTES | EXPOSURE_ATTRIBUTES):
            return

        exposure_changed = bool(changes & EXPOSURE_ATTRIBUTES)
        if exposure_changed:
            self._async_update_legacy_exposure(entity_id)

        if exposure_changed or self.should_expose(entity_id):
            self.async_schedule_google_sync_all()

    @property
    @override
    def enabled(self):
        """Return if Google is enabled."""
        return True

    @property
    @override
    def entity_config(self):
        """Return entity config."""
        return self._config.get(CONF_ENTITY_CONFIG) or {}

    @property
    @override
    def secure_devices_pin(self):
        """Return entity config."""
        return self._config.get(CONF_SECURE_DEVICES_PIN)

    @property
    @override
    def should_report_state(self):
        """Return if states should be proactively reported."""
        return self._config.get(CONF_REPORT_STATE)

    @override
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

    @override
    def get_local_webhook_id(self, agent_user_id):
        """Return the webhook ID for a given agent user id via the local SDK."""
        if data := self._store.agent_user_ids.get(agent_user_id):
            return data[STORE_GOOGLE_LOCAL_WEBHOOK_ID]
        return None

    @override
    def get_agent_user_id_from_context(self, context):
        """Get agent user ID making request."""
        return context.user_id

    @override
    def get_agent_user_id_from_webhook(self, webhook_id):
        """Map webhook ID to a Google agent user ID.

        Return None if no agent user id is found for the webhook_id.
        """
        for agent_user_id, agent_user_data in self._store.agent_user_ids.items():
            if agent_user_data[STORE_GOOGLE_LOCAL_WEBHOOK_ID] == webhook_id:
                return agent_user_id

        return None

    @override
    def should_expose(self, entity_id: str) -> bool:
        """Return if entity should be exposed."""
        return async_should_expose(self.hass, DOMAIN, entity_id)

    def _should_expose_by_default(
        self, entity_id: str, *, auxiliary_entity: bool
    ) -> bool:
        """Return if entity's domain is exposed by default per YAML configuration."""
        cache_key = (entity_id, auxiliary_entity)
        if (cached := self._should_expose_by_default_cache.get(cache_key)) is not None:
            return cached

        expose_by_default = self._config.get(CONF_EXPOSE_BY_DEFAULT)
        exposed_domains = self._config.get(CONF_EXPOSED_DOMAINS)

        domain_exposed_by_default = (
            expose_by_default and split_entity_id(entity_id)[0] in exposed_domains
        )

        # Expose an entity by default if the entity's domain is exposed by default
        # and the entity is not a config or diagnostic entity
        result = domain_exposed_by_default and not auxiliary_entity
        self._should_expose_by_default_cache[cache_key] = result
        return result

    @callback
    def _async_update_legacy_exposure(self, entity_id: str) -> None:
        """Set the entity's YAML-configured exposure in the shared store.

        Kept in memory only, so exposure reverts to the UI-driven store as
        soon as YAML no longer has an opinion, including across a restart
        with the domain, or the whole configuration, removed.
        """
        explicit_expose = self.entity_config.get(entity_id, {}).get(CONF_EXPOSE)
        if explicit_expose is not None:
            async_set_entity_locked(self.hass, DOMAIN, entity_id, explicit_expose)
            return

        entity_registry = er.async_get(self.hass)
        registry_entry = entity_registry.async_get(entity_id)
        if registry_entry:
            auxiliary_entity = (
                registry_entry.entity_category is not None
                or registry_entry.hidden_by is not None
            )
        else:
            auxiliary_entity = False

        should_expose_by_default = self._should_expose_by_default(
            entity_id, auxiliary_entity=auxiliary_entity
        )
        async_set_entity_locked(
            self.hass, DOMAIN, entity_id, True if should_expose_by_default else None
        )

    @override
    def should_2fa(self, state):
        """If an entity should have 2FA checked."""
        return True

    @override
    async def _async_request_sync_devices(self, agent_user_id: str) -> HTTPStatus:
        if CONF_SERVICE_ACCOUNT in self._config:
            return await self.async_call_homegraph_api(
                REQUEST_SYNC_BASE_URL, {"agentUserId": agent_user_id}
            )

        _LOGGER.error("No configuration for request_sync available")
        return HTTPStatus.INTERNAL_SERVER_ERROR

    @override
    async def async_connect_agent_user(self, agent_user_id: str):
        """Add a synced and known agent_user_id.

        Called before sending a sync response to Google.
        """
        self._store.add_agent_user_id(agent_user_id)

    @override
    async def async_disconnect_agent_user(self, agent_user_id: str):
        """Turn off report state and disable further state reporting.

        Called when:
         - The user disconnects their account from Google.
         - When the cloud configuration is initialized
         - When sync entities fails with 404
        """
        self._store.pop_agent_user_id(agent_user_id)

    @callback
    @override
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
        except TimeoutError, ClientError:
            _LOGGER.error("Could not contact %s", url)
            return HTTPStatus.INTERNAL_SERVER_ERROR

    @override
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
            # and that will store the correct agent user id
            # to be used for local requests
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
