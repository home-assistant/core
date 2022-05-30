"""
Connect two Home Assistant instances via the Websocket API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/remote_homeassistant/
"""
import asyncio
import copy
import fnmatch
import inspect
import logging
import re
from contextlib import suppress

import aiohttp
import homeassistant.components.websocket_api.auth as api
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (CONF_ABOVE, CONF_ACCESS_TOKEN, CONF_BELOW,
                                 CONF_DOMAINS, CONF_ENTITIES, CONF_ENTITY_ID,
                                 CONF_EXCLUDE, CONF_HOST, CONF_INCLUDE,
                                 CONF_PORT, CONF_UNIT_OF_MEASUREMENT,
                                 CONF_VERIFY_SSL, EVENT_CALL_SERVICE,
                                 EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED,
                                 SERVICE_RELOAD)
from homeassistant.core import (Context, EventOrigin, HomeAssistant, callback,
                                split_entity_id)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.setup import async_setup_component

from custom_components.remote_homeassistant.views import DiscoveryInfoView

from .const import (CONF_EXCLUDE_DOMAINS, CONF_EXCLUDE_ENTITIES,
                    CONF_INCLUDE_DOMAINS, CONF_INCLUDE_ENTITIES,
                    CONF_LOAD_COMPONENTS, CONF_OPTIONS, CONF_REMOTE_CONNECTION,
                    CONF_SERVICE_PREFIX, CONF_SERVICES, CONF_UNSUB_LISTENER,
                    DOMAIN, REMOTE_ID)
from .proxy_services import ProxyServices
from .rest_api import UnsupportedVersion, async_get_discovery_info

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CONF_INSTANCES = "instances"
CONF_SECURE = "secure"
CONF_SUBSCRIBE_EVENTS = "subscribe_events"
CONF_ENTITY_PREFIX = "entity_prefix"
CONF_FILTER = "filter"

STATE_INIT = "initializing"
STATE_CONNECTING = "connecting"
STATE_CONNECTED = "connected"
STATE_AUTH_INVALID = "auth_invalid"
STATE_AUTH_REQUIRED = "auth_required"
STATE_RECONNECTING = "reconnecting"
STATE_DISCONNECTED = "disconnected"

DEFAULT_ENTITY_PREFIX = ""

INSTANCES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=8123): cv.port,
        vol.Optional(CONF_SECURE, default=False): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Optional(CONF_EXCLUDE, default={}): vol.Schema(
            {
                vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        ),
        vol.Optional(CONF_INCLUDE, default={}): vol.Schema(
            {
                vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
                vol.Optional(CONF_DOMAINS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        ),
        vol.Optional(CONF_FILTER, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_ENTITY_ID): cv.string,
                        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
                        vol.Optional(CONF_ABOVE): vol.Coerce(float),
                        vol.Optional(CONF_BELOW): vol.Coerce(float),
                    }
                )
            ],
        ),
        vol.Optional(CONF_SUBSCRIBE_EVENTS): cv.ensure_list,
        vol.Optional(CONF_ENTITY_PREFIX, default=DEFAULT_ENTITY_PREFIX): cv.string,
        vol.Optional(CONF_LOAD_COMPONENTS): cv.ensure_list,
        vol.Required(CONF_SERVICE_PREFIX, default="remote_"): cv.string,
        vol.Optional(CONF_SERVICES): cv.ensure_list,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_INSTANCES): vol.All(
                    cv.ensure_list, [INSTANCES_SCHEMA]
                ),
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

HEARTBEAT_INTERVAL = 20
HEARTBEAT_TIMEOUT = 5

INTERNALLY_USED_EVENTS = [EVENT_STATE_CHANGED]


def async_yaml_to_config_entry(instance_conf):
    """Convert YAML config into data and options used by a config entry."""
    conf = instance_conf.copy()
    options = {}

    if CONF_INCLUDE in conf:
        include = conf.pop(CONF_INCLUDE)
        if CONF_ENTITIES in include:
            options[CONF_INCLUDE_ENTITIES] = include[CONF_ENTITIES]
        if CONF_DOMAINS in include:
            options[CONF_INCLUDE_DOMAINS] = include[CONF_DOMAINS]

    if CONF_EXCLUDE in conf:
        exclude = conf.pop(CONF_EXCLUDE)
        if CONF_ENTITIES in exclude:
            options[CONF_EXCLUDE_ENTITIES] = exclude[CONF_ENTITIES]
        if CONF_DOMAINS in exclude:
            options[CONF_EXCLUDE_DOMAINS] = exclude[CONF_DOMAINS]

    for option in [
        CONF_FILTER,
        CONF_SUBSCRIBE_EVENTS,
        CONF_ENTITY_PREFIX,
        CONF_LOAD_COMPONENTS,
        CONF_SERVICE_PREFIX,
        CONF_SERVICES,
    ]:
        if option in conf:
            options[option] = conf.pop(option)

    return conf, options


async def _async_update_config_entry_if_from_yaml(hass, entries_by_id, conf):
    """Update a config entry with the latest yaml."""
    try:
        info = await async_get_discovery_info(
            hass,
            conf[CONF_HOST],
            conf[CONF_PORT],
            conf[CONF_SECURE],
            conf[CONF_ACCESS_TOKEN],
            conf[CONF_VERIFY_SSL],
        )
    except Exception:
        _LOGGER.exception(f"reload of {conf[CONF_HOST]} failed")
    else:
        entry = entries_by_id.get(info["uuid"])
        if entry:
            data, options = async_yaml_to_config_entry(conf)
            hass.config_entries.async_update_entry(entry, data=data, options=options)


async def setup_remote_instance(hass: HomeAssistantType):
    hass.http.register_view(DiscoveryInfoView())


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the remote_homeassistant component."""
    hass.data.setdefault(DOMAIN, {})

    async def _handle_reload(service):
        """Handle reload service call."""
        config = await async_integration_yaml_config(hass, DOMAIN)

        if not config or DOMAIN not in config:
            return

        current_entries = hass.config_entries.async_entries(DOMAIN)
        entries_by_id = {entry.unique_id: entry for entry in current_entries}

        instances = config[DOMAIN][CONF_INSTANCES]
        update_tasks = [
            _async_update_config_entry_if_from_yaml(hass, entries_by_id, instance)
            for instance in instances
        ]

        await asyncio.gather(*update_tasks)

    hass.async_create_task(setup_remote_instance(hass))

    hass.helpers.service.async_register_admin_service(
        DOMAIN,
        SERVICE_RELOAD,
        _handle_reload,
    )

    instances = config.get(DOMAIN, {}).get(CONF_INSTANCES, [])
    for instance in instances:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=instance
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Remote Home-Assistant from a config entry."""
    _async_import_options_from_yaml(hass, entry)
    if entry.unique_id == REMOTE_ID:
        hass.async_create_task(setup_remote_instance(hass))
        return True
    else:
        remote = RemoteConnection(hass, entry)

        hass.data[DOMAIN][entry.entry_id] = {
            CONF_REMOTE_CONNECTION: remote,
            CONF_UNSUB_LISTENER: entry.add_update_listener(_update_listener),
        }

        async def setup_components_and_platforms():
            """Set up platforms and initiate connection."""
            for domain in entry.options.get(CONF_LOAD_COMPONENTS, []):
                hass.async_create_task(async_setup_component(hass, domain, {}))

            await asyncio.gather(
                *[
                    hass.config_entries.async_forward_entry_setup(entry, platform)
                    for platform in PLATFORMS
                ]
            )
            await remote.async_connect()

        hass.async_create_task(setup_components_and_platforms())

        return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[CONF_REMOTE_CONNECTION].async_stop()
        data[CONF_UNSUB_LISTENER]()

    return unload_ok


@callback
def _async_import_options_from_yaml(hass: HomeAssistant, entry: ConfigEntry):
    """Import options from YAML into options section of config entry."""
    if CONF_OPTIONS in entry.data:
        data = entry.data.copy()
        options = data.pop(CONF_OPTIONS)
        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def _update_listener(hass, config_entry):
    """Update listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class RemoteConnection(object):
    """A Websocket connection to a remote home-assistant instance."""

    def __init__(self, hass, config_entry):
        """Initialize the connection."""
        self._hass = hass
        self._entry = config_entry
        self._secure = config_entry.data.get(CONF_SECURE, False)
        self._verify_ssl = config_entry.data.get(CONF_VERIFY_SSL, False)
        self._access_token = config_entry.data.get(CONF_ACCESS_TOKEN)

        # see homeassistant/components/influxdb/__init__.py
        # for include/exclude logic
        self._whitelist_e = set(config_entry.options.get(CONF_INCLUDE_ENTITIES, []))
        self._whitelist_d = set(config_entry.options.get(CONF_INCLUDE_DOMAINS, []))
        self._blacklist_e = set(config_entry.options.get(CONF_EXCLUDE_ENTITIES, []))
        self._blacklist_d = set(config_entry.options.get(CONF_EXCLUDE_DOMAINS, []))

        self._filter = [
            {
                CONF_ENTITY_ID: re.compile(fnmatch.translate(f.get(CONF_ENTITY_ID)))
                if f.get(CONF_ENTITY_ID)
                else None,
                CONF_UNIT_OF_MEASUREMENT: f.get(CONF_UNIT_OF_MEASUREMENT),
                CONF_ABOVE: f.get(CONF_ABOVE),
                CONF_BELOW: f.get(CONF_BELOW),
            }
            for f in config_entry.options.get(CONF_FILTER, [])
        ]

        self._subscribe_events = set(
            config_entry.options.get(CONF_SUBSCRIBE_EVENTS, []) + INTERNALLY_USED_EVENTS
        )
        self._entity_prefix = config_entry.options.get(CONF_ENTITY_PREFIX, "")

        self._connection = None
        self._heartbeat_task = None
        self._is_stopping = False
        self._entities = set()
        self._all_entity_names = set()
        self._handlers = {}
        self._remove_listener = None
        self.proxy_services = ProxyServices(hass, config_entry, self)

        self.set_connection_state(STATE_CONNECTING)

        self.__id = 1

    def _prefixed_entity_id(self, entity_id):
        if self._entity_prefix:
            domain, object_id = split_entity_id(entity_id)
            object_id = self._entity_prefix + object_id
            entity_id = domain + "." + object_id
            return entity_id
        return entity_id

    def set_connection_state(self, state):
        """Change current connection state."""
        signal = f"remote_homeassistant_{self._entry.unique_id}"
        async_dispatcher_send(self._hass, signal, state)

    @callback
    def _get_url(self):
        """Get url to connect to."""
        return "%s://%s:%s/api/websocket" % (
            "wss" if self._secure else "ws",
            self._entry.data[CONF_HOST],
            self._entry.data[CONF_PORT],
        )

    async def async_connect(self):
        """Connect to remote home-assistant websocket..."""

        async def _async_stop_handler(event):
            """Stop when Home Assistant is shutting down."""
            await self.async_stop()

        async def _async_instance_get_info():
            """Fetch discovery info from remote instance."""
            try:
                return await async_get_discovery_info(
                    self._hass,
                    self._entry.data[CONF_HOST],
                    self._entry.data[CONF_PORT],
                    self._secure,
                    self._access_token,
                    self._verify_ssl,
                )
            except OSError:
                _LOGGER.exception("failed to connect")
            except UnsupportedVersion:
                _LOGGER.error("Unsupported version, at least 0.111 is required.")
            except Exception:
                _LOGGER.exception("failed to fetch instance info")
            return None

        @callback
        def _async_instance_id_match(info):
            """Verify if remote instance id matches the expected id."""
            if not info:
                return False
            if info and info["uuid"] != self._entry.unique_id:
                _LOGGER.error(
                    "instance id not matching: %s != %s",
                    info["uuid"],
                    self._entry.unique_id,
                )
                return False
            return True

        url = self._get_url()

        session = async_get_clientsession(self._hass, self._verify_ssl)
        self.set_connection_state(STATE_CONNECTING)

        while True:
            info = await _async_instance_get_info()

            # Verify we are talking to correct instance
            if not _async_instance_id_match(info):
                self.set_connection_state(STATE_RECONNECTING)
                await asyncio.sleep(10)
                continue

            try:
                _LOGGER.info("Connecting to %s", url)
                self._connection = await session.ws_connect(url)
            except aiohttp.client_exceptions.ClientError:
                _LOGGER.error("Could not connect to %s, retry in 10 seconds...", url)
                self.set_connection_state(STATE_RECONNECTING)
                await asyncio.sleep(10)
            else:
                _LOGGER.info("Connected to home-assistant websocket at %s", url)
                break

        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop_handler)

        device_registry = await dr.async_get_registry(self._hass)
        device_registry.async_get_or_create(
            config_entry_id=self._entry.entry_id,
            identifiers={(DOMAIN, f"remote_{self._entry.unique_id}")},
            name=info.get("location_name"),
            manufacturer="Home Assistant",
            model=info.get("installation_type"),
            sw_version=info.get("ha_version"),
        )

        asyncio.ensure_future(self._recv())
        self._heartbeat_task = self._hass.loop.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to remote instance."""
        while not self._connection.closed:
            await asyncio.sleep(HEARTBEAT_INTERVAL)

            _LOGGER.debug("Sending ping")
            event = asyncio.Event()

            def resp(message):
                _LOGGER.debug("Got pong: %s", message)
                event.set()

            await self.call(resp, "ping")

            try:
                await asyncio.wait_for(event.wait(), HEARTBEAT_TIMEOUT)
            except asyncio.TimeoutError:
                _LOGGER.error("heartbeat failed")

                # Schedule closing on event loop to avoid deadlock
                asyncio.ensure_future(self._connection.close())
                break

    async def async_stop(self):
        """Close connection."""
        self._is_stopping = True
        if self._connection is not None:
            await self._connection.close()
        await self.proxy_services.unload()

    def _next_id(self):
        _id = self.__id
        self.__id += 1
        return _id

    async def call(self, callback, message_type, **extra_args):
        _id = self._next_id()
        self._handlers[_id] = callback
        try:
            await self._connection.send_json(
                {"id": _id, "type": message_type, **extra_args}
            )
        except aiohttp.client_exceptions.ClientError as err:
            _LOGGER.error("remote websocket connection closed: %s", err)
            await self._disconnected()

    async def _disconnected(self):
        # Remove all published entries
        for entity in self._entities:
            self._hass.states.async_remove(entity)
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._remove_listener is not None:
            self._remove_listener()

        self.set_connection_state(STATE_DISCONNECTED)
        self._heartbeat_task = None
        self._remove_listener = None
        self._entities = set()
        self._all_entity_names = set()
        if not self._is_stopping:
            asyncio.ensure_future(self.async_connect())

    async def _recv(self):
        while not self._connection.closed:
            try:
                data = await self._connection.receive()
            except aiohttp.client_exceptions.ClientError as err:
                _LOGGER.error("remote websocket connection closed: %s", err)
                break

            if not data:
                break

            if data.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSING,
            ):
                _LOGGER.debug("websocket connection is closing")
                break

            if data.type == aiohttp.WSMsgType.ERROR:
                _LOGGER.error("websocket connection had an error")
                break

            try:
                message = data.json()
            except TypeError as err:
                _LOGGER.error("could not decode data (%s) as json: %s", data, err)
                break

            if message is None:
                break

            _LOGGER.debug("received: %s", message)

            if message["type"] == api.TYPE_AUTH_OK:
                self.set_connection_state(STATE_CONNECTED)
                await self._init()

            elif message["type"] == api.TYPE_AUTH_REQUIRED:
                if self._access_token:
                    data = {"type": api.TYPE_AUTH, "access_token": self._access_token}
                else:
                    _LOGGER.error("Access token required, but not provided")
                    self.set_connection_state(STATE_AUTH_REQUIRED)
                    return
                try:
                    await self._connection.send_json(data)
                except Exception as err:
                    _LOGGER.error("could not send data to remote connection: %s", err)
                    break

            elif message["type"] == api.TYPE_AUTH_INVALID:
                _LOGGER.error("Auth invalid, check your access token")
                self.set_connection_state(STATE_AUTH_INVALID)
                await self._connection.close()
                return

            else:
                callback = self._handlers.get(message["id"])
                if callback is not None:
                    if inspect.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)

        await self._disconnected()

    async def _init(self):
        async def forward_event(event):
            """Send local event to remote instance.

            The affected entity_id has to origin from that remote instance,
            otherwise the event is dicarded.
            """
            event_data = event.data
            service_data = event_data["service_data"]

            if not service_data:
                return

            entity_ids = service_data.get("entity_id", None)

            if not entity_ids:
                return

            if isinstance(entity_ids, str):
                entity_ids = (entity_ids.lower(),)

            entities = {entity_id.lower() for entity_id in self._entities}

            entity_ids = entities.intersection(entity_ids)

            if not entity_ids:
                return

            if self._entity_prefix:

                def _remove_prefix(entity_id):
                    domain, object_id = split_entity_id(entity_id)
                    object_id = object_id.replace(self._entity_prefix.lower(), "", 1)
                    return domain + "." + object_id

                entity_ids = {_remove_prefix(entity_id) for entity_id in entity_ids}

            event_data = copy.deepcopy(event_data)
            event_data["service_data"]["entity_id"] = list(entity_ids)

            # Remove service_call_id parameter - websocket API
            # doesn't accept that one
            event_data.pop("service_call_id", None)

            _id = self._next_id()
            data = {"id": _id, "type": event.event_type, **event_data}

            _LOGGER.debug("forward event: %s", data)

            try:
                await self._connection.send_json(data)
            except Exception as err:
                _LOGGER.error("could not send data to remote connection: %s", err)
                await self._disconnected()

        def state_changed(entity_id, state, attr):
            """Publish remote state change on local instance."""
            domain, object_id = split_entity_id(entity_id)

            self._all_entity_names.add(entity_id)

            if entity_id in self._blacklist_e or domain in self._blacklist_d:
                return

            if (
                (self._whitelist_e or self._whitelist_d)
                and entity_id not in self._whitelist_e
                and domain not in self._whitelist_d
            ):
                return

            for f in self._filter:
                if f[CONF_ENTITY_ID] and not f[CONF_ENTITY_ID].match(entity_id):
                    continue
                if f[CONF_UNIT_OF_MEASUREMENT]:
                    if CONF_UNIT_OF_MEASUREMENT not in attr:
                        continue
                    if f[CONF_UNIT_OF_MEASUREMENT] != attr[CONF_UNIT_OF_MEASUREMENT]:
                        continue
                try:
                    if f[CONF_BELOW] and float(state) < f[CONF_BELOW]:
                        _LOGGER.info(
                            "%s: ignoring state '%s', because " "below '%s'",
                            entity_id,
                            state,
                            f[CONF_BELOW],
                        )
                        return
                    if f[CONF_ABOVE] and float(state) > f[CONF_ABOVE]:
                        _LOGGER.info(
                            "%s: ignoring state '%s', because " "above '%s'",
                            entity_id,
                            state,
                            f[CONF_ABOVE],
                        )
                        return
                except ValueError:
                    pass

            entity_id = self._prefixed_entity_id(entity_id)

            # Add local customization data
            if DATA_CUSTOMIZE in self._hass.data:
                attr.update(self._hass.data[DATA_CUSTOMIZE].get(entity_id))

            self._entities.add(entity_id)
            self._hass.states.async_set(entity_id, state, attr)

        def fire_event(message):
            """Publish remove event on local instance."""
            if message["type"] == "result":
                return

            if message["type"] != "event":
                return

            if message["event"]["event_type"] == "state_changed":
                data = message["event"]["data"]
                entity_id = data["entity_id"]
                if not data["new_state"]:
                    entity_id = self._prefixed_entity_id(entity_id)
                    # entity was removed in the remote instance
                    with suppress(ValueError, AttributeError, KeyError):
                        self._entities.remove(entity_id)
                    with suppress(ValueError, AttributeError, KeyError):
                        self._all_entity_names.remove(entity_id)
                    self._hass.states.async_remove(entity_id)
                    return

                state = data["new_state"]["state"]
                attr = data["new_state"]["attributes"]
                state_changed(entity_id, state, attr)
            else:
                event = message["event"]
                self._hass.bus.async_fire(
                    event_type=event["event_type"],
                    event_data=event["data"],
                    context=Context(
                        id=event["context"].get("id"),
                        user_id=event["context"].get("user_id"),
                        parent_id=event["context"].get("parent_id"),
                    ),
                    origin=EventOrigin.remote,
                )

        def got_states(message):
            """Called when list of remote states is available."""
            for entity in message["result"]:
                entity_id = entity["entity_id"]
                state = entity["state"]
                attributes = entity["attributes"]

                state_changed(entity_id, state, attributes)

        self._remove_listener = self._hass.bus.async_listen(
            EVENT_CALL_SERVICE, forward_event
        )

        for event in self._subscribe_events:
            await self.call(fire_event, "subscribe_events", event_type=event)

        await self.call(got_states, "get_states")

        await self.proxy_services.load()
