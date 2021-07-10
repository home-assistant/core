"""Helper classes for Google Assistant integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import gather
from collections.abc import Mapping
import logging
import pprint

from aiohttp.web import json_response

from homeassistant.components import webhook
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    CLOUD_NEVER_EXPOSED_ENTITIES,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State, callback
from homeassistant.helpers.area_registry import AreaEntry
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store

from . import trait
from .const import (
    CONF_ALIASES,
    CONF_ROOM_HINT,
    DEVICE_CLASS_TO_GOOGLE_TYPES,
    DOMAIN,
    DOMAIN_TO_GOOGLE_TYPES,
    ERR_FUNCTION_NOT_SUPPORTED,
    NOT_EXPOSE_LOCAL,
    SOURCE_LOCAL,
    STORE_AGENT_USER_IDS,
)
from .error import SmartHomeError

SYNC_DELAY = 15
_LOGGER = logging.getLogger(__name__)


async def _get_entity_and_device(
    hass, entity_id
) -> tuple[RegistryEntry, DeviceEntry] | None:
    """Fetch the entity and device entries for a entity_id."""
    dev_reg, ent_reg = await gather(
        hass.helpers.device_registry.async_get_registry(),
        hass.helpers.entity_registry.async_get_registry(),
    )

    entity_entry = ent_reg.async_get(entity_id)
    if not entity_entry:
        return None, None
    device_entry = dev_reg.devices.get(entity_entry.device_id)
    return entity_entry, device_entry


async def _get_area(hass, entity_entry, device_entry) -> AreaEntry | None:
    """Calculate the area for an entity."""
    if entity_entry and entity_entry.area_id:
        area_id = entity_entry.area_id
    elif device_entry and device_entry.area_id:
        area_id = device_entry.area_id
    else:
        return None

    area_reg = await hass.helpers.area_registry.async_get_registry()
    return area_reg.areas.get(area_id)


async def _get_device_info(device_entry) -> dict[str, str] | None:
    """Retrieve the device info for a device."""
    if not device_entry:
        return None

    device_info = {}
    if device_entry.manufacturer:
        device_info["manufacturer"] = device_entry.manufacturer
    if device_entry.model:
        device_info["model"] = device_entry.model
    if device_entry.sw_version:
        device_info["swVersion"] = device_entry.sw_version
    return device_info


class AbstractConfig(ABC):
    """Hold the configuration for Google Assistant."""

    _unsub_report_state = None

    def __init__(self, hass):
        """Initialize abstract config."""
        self.hass = hass
        self._store = None
        self._google_sync_unsub = {}
        self._local_sdk_active = False

    async def async_initialize(self):
        """Perform async initialization of config."""
        self._store = GoogleConfigStore(self.hass)
        await self._store.async_load()

        if self.hass.state == CoreState.running:
            await self.async_sync_entities_all()
            return

        async def sync_google(_):
            """Sync entities to Google."""
            await self.async_sync_entities_all()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, sync_google)

    @property
    def enabled(self):
        """Return if Google is enabled."""
        return False

    @property
    def entity_config(self):
        """Return entity config."""
        return {}

    @property
    def secure_devices_pin(self):
        """Return entity config."""
        return None

    @property
    def is_reporting_state(self):
        """Return if we're actively reporting states."""
        return self._unsub_report_state is not None

    @property
    def is_local_sdk_active(self):
        """Return if we're actively accepting local messages."""
        return self._local_sdk_active

    @property
    def should_report_state(self):
        """Return if states should be proactively reported."""
        return False

    @property
    def local_sdk_webhook_id(self):
        """Return the local SDK webhook ID.

        Return None to disable the local SDK.
        """
        return None

    @property
    def local_sdk_user_id(self):
        """Return the user ID to be used for actions received via the local SDK."""
        raise NotImplementedError

    @abstractmethod
    def get_agent_user_id(self, context):
        """Get agent user ID from context."""

    @abstractmethod
    def should_expose(self, state) -> bool:
        """Return if entity should be exposed."""

    def should_2fa(self, state):
        """If an entity should have 2FA checked."""
        # pylint: disable=no-self-use
        return True

    async def async_report_state(self, message, agent_user_id: str):
        """Send a state report to Google."""
        raise NotImplementedError

    async def async_report_state_all(self, message):
        """Send a state report to Google for all previously synced users."""
        jobs = [
            self.async_report_state(message, agent_user_id)
            for agent_user_id in self._store.agent_user_ids
        ]
        await gather(*jobs)

    @callback
    def async_enable_report_state(self):
        """Enable proactive mode."""
        # Circular dep
        # pylint: disable=import-outside-toplevel
        from .report_state import async_enable_report_state

        if self._unsub_report_state is None:
            self._unsub_report_state = async_enable_report_state(self.hass, self)

    @callback
    def async_disable_report_state(self):
        """Disable report state."""
        if self._unsub_report_state is not None:
            self._unsub_report_state()
            self._unsub_report_state = None

    async def async_sync_entities(self, agent_user_id: str):
        """Sync all entities to Google."""
        # Remove any pending sync
        self._google_sync_unsub.pop(agent_user_id, lambda: None)()
        status = await self._async_request_sync_devices(agent_user_id)
        if status == 404:
            await self.async_disconnect_agent_user(agent_user_id)
        return status

    async def async_sync_entities_all(self):
        """Sync all entities to Google for all registered agents."""
        res = await gather(
            *[
                self.async_sync_entities(agent_user_id)
                for agent_user_id in self._store.agent_user_ids
            ]
        )
        return max(res, default=204)

    @callback
    def async_schedule_google_sync(self, agent_user_id: str):
        """Schedule a sync."""

        async def _schedule_callback(_now):
            """Handle a scheduled sync callback."""
            self._google_sync_unsub.pop(agent_user_id, None)
            await self.async_sync_entities(agent_user_id)

        self._google_sync_unsub.pop(agent_user_id, lambda: None)()

        self._google_sync_unsub[agent_user_id] = async_call_later(
            self.hass, SYNC_DELAY, _schedule_callback
        )

    @callback
    def async_schedule_google_sync_all(self):
        """Schedule a sync for all registered agents."""
        for agent_user_id in self._store.agent_user_ids:
            self.async_schedule_google_sync(agent_user_id)

    async def _async_request_sync_devices(self, agent_user_id: str) -> int:
        """Trigger a sync with Google.

        Return value is the HTTP status code of the sync request.
        """
        raise NotImplementedError

    async def async_connect_agent_user(self, agent_user_id: str):
        """Add an synced and known agent_user_id.

        Called when a completed sync response have been sent to Google.
        """
        self._store.add_agent_user_id(agent_user_id)

    async def async_disconnect_agent_user(self, agent_user_id: str):
        """Turn off report state and disable further state reporting.

        Called when the user disconnects their account from Google.
        """
        self._store.pop_agent_user_id(agent_user_id)

    @callback
    def async_enable_local_sdk(self):
        """Enable the local SDK."""
        webhook_id = self.local_sdk_webhook_id

        if webhook_id is None:
            return

        try:
            webhook.async_register(
                self.hass,
                DOMAIN,
                "Local Support",
                webhook_id,
                self._handle_local_webhook,
            )
        except ValueError:
            _LOGGER.info("Webhook handler is already defined!")
            return

        self._local_sdk_active = True

    @callback
    def async_disable_local_sdk(self):
        """Disable the local SDK."""
        if not self._local_sdk_active:
            return

        webhook.async_unregister(self.hass, self.local_sdk_webhook_id)
        self._local_sdk_active = False

    async def _handle_local_webhook(self, hass, webhook_id, request):
        """Handle an incoming local SDK message."""
        # Circular dep
        # pylint: disable=import-outside-toplevel
        from . import smart_home

        payload = await request.json()

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Received local message:\n%s\n", pprint.pformat(payload))

        if not self.enabled:
            return json_response(smart_home.turned_off_response(payload))

        result = await smart_home.async_handle_message(
            self.hass, self, self.local_sdk_user_id, payload, SOURCE_LOCAL
        )

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Responding to local message:\n%s\n", pprint.pformat(result))

        return json_response(result)


class GoogleConfigStore:
    """A configuration store for google assistant."""

    _STORAGE_VERSION = 1
    _STORAGE_KEY = DOMAIN

    def __init__(self, hass):
        """Initialize a configuration store."""
        self._hass = hass
        self._store = Store(hass, self._STORAGE_VERSION, self._STORAGE_KEY)
        self._data = {STORE_AGENT_USER_IDS: {}}

    @property
    def agent_user_ids(self):
        """Return a list of connected agent user_ids."""
        return self._data[STORE_AGENT_USER_IDS]

    @callback
    def add_agent_user_id(self, agent_user_id):
        """Add an agent user id to store."""
        if agent_user_id not in self._data[STORE_AGENT_USER_IDS]:
            self._data[STORE_AGENT_USER_IDS][agent_user_id] = {}
            self._store.async_delay_save(lambda: self._data, 1.0)

    @callback
    def pop_agent_user_id(self, agent_user_id):
        """Remove agent user id from store."""
        if agent_user_id in self._data[STORE_AGENT_USER_IDS]:
            self._data[STORE_AGENT_USER_IDS].pop(agent_user_id, None)
            self._store.async_delay_save(lambda: self._data, 1.0)

    async def async_load(self):
        """Store current configuration to disk."""
        data = await self._store.async_load()
        if data:
            self._data = data


class RequestData:
    """Hold data associated with a particular request."""

    def __init__(
        self,
        config: AbstractConfig,
        user_id: str,
        source: str,
        request_id: str,
        devices: list[dict] | None,
    ) -> None:
        """Initialize the request data."""
        self.config = config
        self.source = source
        self.request_id = request_id
        self.context = Context(user_id=user_id)
        self.devices = devices

    @property
    def is_local_request(self):
        """Return if this is a local request."""
        return self.source == SOURCE_LOCAL


def get_google_type(domain, device_class):
    """Google type based on domain and device class."""
    typ = DEVICE_CLASS_TO_GOOGLE_TYPES.get((domain, device_class))

    return typ if typ is not None else DOMAIN_TO_GOOGLE_TYPES[domain]


class GoogleEntity:
    """Adaptation of Entity expressed in Google's terms."""

    def __init__(
        self, hass: HomeAssistant, config: AbstractConfig, state: State
    ) -> None:
        """Initialize a Google entity."""
        self.hass = hass
        self.config = config
        self.state = state
        self._traits = None

    @property
    def entity_id(self):
        """Return entity ID."""
        return self.state.entity_id

    @callback
    def traits(self):
        """Return traits for entity."""
        if self._traits is not None:
            return self._traits

        state = self.state
        domain = state.domain
        attributes = state.attributes
        features = attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if not isinstance(features, int):
            _LOGGER.warning(
                "Entity %s contains invalid supported_features value %s",
                self.entity_id,
                features,
            )
            return []

        device_class = state.attributes.get(ATTR_DEVICE_CLASS)

        self._traits = [
            Trait(self.hass, state, self.config)
            for Trait in trait.TRAITS
            if Trait.supported(domain, features, device_class, attributes)
        ]
        return self._traits

    @callback
    def should_expose(self):
        """If entity should be exposed."""
        return self.config.should_expose(self.state)

    @callback
    def should_expose_local(self) -> bool:
        """Return if the entity should be exposed locally."""
        return (
            self.should_expose()
            and get_google_type(
                self.state.domain, self.state.attributes.get(ATTR_DEVICE_CLASS)
            )
            not in NOT_EXPOSE_LOCAL
            and not self.might_2fa()
        )

    @callback
    def is_supported(self) -> bool:
        """Return if the entity is supported by Google."""
        return bool(self.traits())

    @callback
    def might_2fa(self) -> bool:
        """Return if the entity might encounter 2FA."""
        if not self.config.should_2fa(self.state):
            return False

        return self.might_2fa_traits()

    @callback
    def might_2fa_traits(self) -> bool:
        """Return if the entity might encounter 2FA based on just traits."""
        state = self.state
        domain = state.domain
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)

        return any(
            trait.might_2fa(domain, features, device_class) for trait in self.traits()
        )

    async def sync_serialize(self, agent_user_id):
        """Serialize entity for a SYNC response.

        https://developers.google.com/actions/smarthome/create-app#actiondevicessync
        """
        state = self.state

        entity_config = self.config.entity_config.get(state.entity_id, {})
        name = (entity_config.get(CONF_NAME) or state.name).strip()
        domain = state.domain
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        entity_entry, device_entry = await _get_entity_and_device(
            self.hass, state.entity_id
        )

        traits = self.traits()

        device_type = get_google_type(domain, device_class)

        device = {
            "id": state.entity_id,
            "name": {"name": name},
            "attributes": {},
            "traits": [trait.name for trait in traits],
            "willReportState": self.config.should_report_state,
            "type": device_type,
        }

        # use aliases
        aliases = entity_config.get(CONF_ALIASES)
        if aliases:
            device["name"]["nicknames"] = [name] + aliases

        if self.config.is_local_sdk_active and self.should_expose_local():
            device["otherDeviceIds"] = [{"deviceId": self.entity_id}]
            device["customData"] = {
                "webhookId": self.config.local_sdk_webhook_id,
                "httpPort": self.hass.http.server_port,
                "httpSSL": self.hass.config.api.use_ssl,
                "uuid": await self.hass.helpers.instance_id.async_get(),
                "baseUrl": get_url(self.hass, prefer_external=True),
                "proxyDeviceId": agent_user_id,
            }

        for trt in traits:
            device["attributes"].update(trt.sync_attributes())

        room = entity_config.get(CONF_ROOM_HINT)
        if room:
            device["roomHint"] = room
        else:
            area = await _get_area(self.hass, entity_entry, device_entry)
            if area and area.name:
                device["roomHint"] = area.name

        device_info = await _get_device_info(device_entry)
        if device_info:
            device["deviceInfo"] = device_info

        return device

    @callback
    def query_serialize(self):
        """Serialize entity for a QUERY response.

        https://developers.google.com/actions/smarthome/create-app#actiondevicesquery
        """
        state = self.state

        if state.state == STATE_UNAVAILABLE:
            return {"online": False}

        attrs = {"online": True}

        for trt in self.traits():
            deep_update(attrs, trt.query_attributes())

        return attrs

    @callback
    def reachable_device_serialize(self):
        """Serialize entity for a REACHABLE_DEVICE response."""
        return {"verificationId": self.entity_id}

    async def execute(self, data, command_payload):
        """Execute a command.

        https://developers.google.com/actions/smarthome/create-app#actiondevicesexecute
        """
        command = command_payload["command"]
        params = command_payload.get("params", {})
        challenge = command_payload.get("challenge", {})
        executed = False
        for trt in self.traits():
            if trt.can_execute(command, params):
                await trt.execute(command, data, params, challenge)
                executed = True
                break

        if not executed:
            raise SmartHomeError(
                ERR_FUNCTION_NOT_SUPPORTED,
                f"Unable to execute {command} for {self.state.entity_id}",
            )

    @callback
    def async_update(self):
        """Update the entity with latest info from Home Assistant."""
        self.state = self.hass.states.get(self.entity_id)

        if self._traits is None:
            return

        for trt in self._traits:
            trt.state = self.state


def deep_update(target, source):
    """Update a nested dictionary with another nested dictionary."""
    for key, value in source.items():
        if isinstance(value, Mapping):
            target[key] = deep_update(target.get(key, {}), value)
        else:
            target[key] = value
    return target


@callback
def async_get_entities(hass, config) -> list[GoogleEntity]:
    """Return all entities that are supported by Google."""
    entities = []
    for state in hass.states.async_all():
        if state.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            continue

        entity = GoogleEntity(hass, config, state)

        if entity.is_supported():
            entities.append(entity)

    return entities
