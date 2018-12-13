"""Support for esphomelib devices."""
import asyncio
import logging
from typing import Any, Dict, List, Union

import attr
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, \
    EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect, \
    async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import HomeAssistantType
# Loading the config flow file will register the flow
from .config_flow import EsphomelibFlowHandler  # noqa

DOMAIN = 'esphomelib'
REQUIREMENTS = ['aioesphomeapi==1.0.0']

STORAGE_KEY = 'esphomelib.data'
STORAGE_VERSION = 1
DATA_STORE = 'esphomelib_store'
DATA_SERIALIZERS = 'esphomelib_serializers'
DATA_CLIENT = 'client'
DATA_RECONNECT_TASK = 'reconnect'
DATA_AVAILABLE = 'available'
DATA_DEVICE_INFO = 'device_info'
DISPATCHER_ON_STATE = 'esphomelib_{}_on_state'
DISPATCHER_ON_LIST = 'esphomelib_{}_on_list'
DISPATCHER_ON_DEVICE_UPDATE = 'esphomelib_{}_on_device_update'
HA_COMPONENTS = ['sensor', 'binary_sensor', 'switch', 'light', 'fan', 'cover']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


async def _cleanup_instance(hass: HomeAssistantType, entry: ConfigEntry):
    data = hass.data[DOMAIN].pop(entry.entry_id)
    client = data[DATA_CLIENT]
    if DATA_RECONNECT_TASK in data:
        data[DATA_RECONNECT_TASK].cancel()
    await client.stop()


def get_or_create_store(hass: HomeAssistantType) -> Store:
    """Get or create the Store module for retained esphomelib data."""
    if DATA_STORE not in hass.data:
        store = Store(hass, STORAGE_VERSION,
                      STORAGE_KEY, encoder=JSONEncoder)
        hass.data[DATA_STORE] = store
    return hass.data[DATA_STORE]


async def async_save_store(hass: HomeAssistantType):
    """Generate dynamic data to store and save it to the filesystem."""
    from aioesphomeapi.client import COMPONENT_TYPE_TO_INFO

    store = get_or_create_store(hass)
    all_store_data = {}
    for entry_id, data in hass.data[DOMAIN].items():
        store_data = all_store_data[entry_id] = {}
        store_data[DATA_DEVICE_INFO] = attr.asdict(data[DATA_DEVICE_INFO])

        for key in COMPONENT_TYPE_TO_INFO:
            if key not in data:
                continue
            comp = store_data[key] = []
            for entity in data[key].values():
                comp.append(attr.asdict(entity.info))

    await store.async_save(all_store_data)


def get_entry_data(hass: HomeAssistantType,
                   key: Union[ConfigEntry, str]) -> Dict[str, Any]:
    """Get the per-config entry data dictionary for a key."""
    if isinstance(key, ConfigEntry):
        key = key.entry_id
    return hass.data[DOMAIN].setdefault(key, {})


async def async_load_store(hass: HomeAssistantType, entry: ConfigEntry):
    """Load the retained data from store and return de-serialized data."""
    from aioesphomeapi.client import COMPONENT_TYPE_TO_INFO, DeviceInfo
    store = get_or_create_store(hass)
    restored = await store.async_load()
    if restored is None or entry.entry_id not in restored:
        return []
    restored = restored[entry.entry_id]

    device_info = DeviceInfo(**restored.pop(DATA_DEVICE_INFO))
    get_entry_data(hass, entry)[DATA_DEVICE_INFO] = device_info
    infos = []
    for key, values in restored.items():
        if key not in COMPONENT_TYPE_TO_INFO:
            continue
        for info in values:
            infos.append(COMPONENT_TYPE_TO_INFO[key](**info))
    return infos


async def _setup_device_registry(hass: HomeAssistantType, entry: ConfigEntry,
                                 device_info):
    """Set up device registry feature for a particular config entry."""
    sw_version = 'esphomelib v' + device_info.esphomelib_version
    if device_info.compilation_time:
        sw_version += ' ({})'.format(device_info.compilation_time)
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={
            (dr.CONNECTION_NETWORK_MAC, device_info.mac_address)
        },
        name=device_info.name,
        manufacturer='espressif',
        model=device_info.model,
        sw_version=sw_version,
    )


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up the esphomelib component."""
    from aioesphomeapi.client import APIClient, APIConnectionError

    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]

    cli = APIClient(hass.loop, host, port, password)
    await cli.start()

    async def on_stop(event):
        """Cleanup the socket client on HA stop."""
        await _cleanup_instance(hass, entry)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop)

    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    entry_data[DATA_CLIENT] = cli
    entry_data[DATA_AVAILABLE] = False

    try_connect = await _setup_auto_reconnect_logic(
        hass, cli, entry.entry_id, host)

    @callback
    def async_on_state(state):
        """Send dispatcher updates when a new state is received."""
        async_dispatcher_send(
            hass, DISPATCHER_ON_STATE.format(entry.entry_id), state)

    async def on_login():
        """Subscribe to states and list entities on successful API login."""
        try:
            device = entry_data[DATA_DEVICE_INFO] = await cli.device_info()
            entry_data[DATA_AVAILABLE] = True

            await _setup_device_registry(hass, entry, device)

            entity_infos = await cli.list_entities()
            async_dispatcher_send(
                hass, DISPATCHER_ON_LIST.format(entry.entry_id),
                entity_infos)
            await cli.subscribe_states(async_on_state)

            hass.async_add_job(async_save_store(hass))
        except APIConnectionError as err:
            _LOGGER.warning("Error getting initial data: %s", err)
            # Re-connection logic will trigger after this
            await cli.disconnect()

    cli.on_login = on_login

    # This is a bit of a hack. complete_task is not await from this coroutine
    # but there's a good reason for it:
    # First, we need to make _sure_ that each platform is fully set up
    # before doing the initial connection attempt. Otherwise the
    # dispatcher callbacks will write into the void.
    # However, we cannot simply await async_forward_entry_setup from within
    # async_setup_entry as that would result in a recursive await
    # So workaround is: complete the entry setup + connection
    # in the pending task queue. It will still be tracked by hass
    # (_pending_tasks) so startup will be delayed correctly until the
    # component is ready.

    async def complete_setup():
        """Complete the config entry setup."""
        for component in HA_COMPONENTS:
            await hass.config_entries.async_forward_entry_setup(
                entry, component)

        infos = await async_load_store(hass, entry)
        async_dispatcher_send(
            hass, DISPATCHER_ON_LIST.format(entry.entry_id), infos)

        # If first connect fails, the next re-connect will be scheduled
        # outside of _pending_task, in order not to delay HA startup
        # indefinitely
        await try_connect(is_disconnect=False)

    hass.async_add_job(complete_setup())
    return True


async def _setup_auto_reconnect_logic(hass: HomeAssistantType, cli, key,
                                      host):
    """Set up the re-connect logic for the API client."""
    from aioesphomeapi.client import APIConnectionError

    async def try_connect(tries=0, is_disconnect=True):
        """Try connecting to the API client. Will retry if not successful."""
        if key not in hass.data[DOMAIN]:
            # When removing/disconnecting manually
            return

        data = get_entry_data(hass, key)
        data[DATA_AVAILABLE] = False
        async_dispatcher_send(hass, DISPATCHER_ON_DEVICE_UPDATE.format(key))

        if tries != 0:
            wait_time = min(2**tries, 300)
            _LOGGER.info("Trying to reconnect in %s seconds.", wait_time)
            await asyncio.sleep(wait_time)

        if is_disconnect and tries == 0:
            # This can happen often depending on WiFi strength.
            # Let's make this an info message ("unavailable" state will
            # be set anyway)
            _LOGGER.info("Disconnected from API.")

        try:
            await cli.connect()
            await cli.login()
        except APIConnectionError as error:
            _LOGGER.info("Can't connect to esphomelib API for %s (%s).",
                         host, error)
            # Schedule re-connect in event loop in order not to delay HA
            # startup. First connect is scheduled in tracked tasks
            data['reconnect'] = hass.loop.create_task(
                try_connect(tries + 1, is_disconnect))
        else:
            _LOGGER.info("Successfully connected to %s", host)

    cli.on_disconnect = try_connect
    return try_connect


async def async_unload_entry(hass, config_entry) -> bool:
    """Unload an esphomelib config entry."""
    await _cleanup_instance(hass, config_entry)

    for component in HA_COMPONENTS:
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    return True


async def async_setup(hass, config):
    """Stub to allow setting up this component.

    Configuration through YAML is not supported at this time.
    """
    return True


async def platform_async_setup_entry(hass: HomeAssistantType,
                                     entry: ConfigEntry,
                                     async_add_entities,
                                     *,
                                     component_key,
                                     info_type,
                                     entity_type,
                                     state_type,
                                     ):
    """Set up an esphomelib platform."""
    get_entry_data(hass, entry).setdefault(component_key, {})

    @callback
    def async_list_entities(infos: List[Any]):
        """Update entities of this platform when entities are listed."""
        old_entities = get_entry_data(hass, entry)[component_key]
        new_entities = {}
        add_entities = []
        for info in infos:
            if not isinstance(info, info_type):
                continue

            if info.key in old_entities:
                # Update existing entity
                entity = old_entities.pop(info.key)
            else:
                # Create new entity
                entity = entity_type(entry.entry_id)
                add_entities.append(entity)
            entity.async_info_update(info)
            new_entities[info.key] = entity

        # Remove old entities
        for entity in old_entities.values():
            hass.async_add_job(entity.async_remove())

        get_entry_data(hass, entry)[component_key] = new_entities
        async_add_entities(add_entities)

    async_dispatcher_connect(
        hass, DISPATCHER_ON_LIST.format(entry.entry_id), async_list_entities)

    @callback
    def async_entity_state(state):
        """Notify the appropriate entity of an updated state."""
        entities = get_entry_data(hass, entry)[component_key]
        if not isinstance(state, state_type):
            return
        if state.key not in entities:
            return
        entity = entities[state.key]
        entity.async_state_update(state)

    async_dispatcher_connect(
        hass, DISPATCHER_ON_STATE.format(entry.entry_id), async_entity_state)

    @callback
    def async_device_state():
        entities = get_entry_data(hass, entry)[component_key]
        for entity in entities.values():
            if entity.hass is not None:
                entity.async_schedule_update_ha_state()

    async_dispatcher_connect(
        hass, DISPATCHER_ON_DEVICE_UPDATE.format(entry.entry_id),
        async_device_state)


class EsphomelibEntity(Entity):
    """Define a generic esphomelib entity."""

    def __init__(self, data_key):
        """Initialize."""
        self._data_key = data_key
        self.info = None
        self._state = None

    @callback
    def async_info_update(self, info):
        """Update the info attribute."""
        self.info = info
        if self.hass is not None:
            self.async_schedule_update_ha_state()

    @callback
    def async_state_update(self, state):
        """Update the state attribute."""
        self._state = state
        if self.hass is not None:
            self.async_schedule_update_ha_state()

    @property
    def _device_data(self):
        return self.hass.data[DOMAIN][self._data_key]

    @property
    def _client(self):
        return self._device_data[DATA_CLIENT]

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        device = self._device_data[DATA_DEVICE_INFO]

        return {
            'connections': {(dr.CONNECTION_NETWORK_MAC, device.mac_address)}
        }

    @property
    def available(self):
        """Return if the entity is available."""
        device = self._device_data['device_info']

        if device.has_deep_sleep:
            # During deep sleep the ESP will not be connectable (by design)
            # For these cases, show it as available
            return True

        return self._device_data['available']

    @property
    def unique_id(self):
        """Return a unique id identifying the entity."""
        if not self.info.unique_id:
            return None
        return self.info.unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.info.name

    @property
    def should_poll(self):
        """Disable polling."""
        return False
