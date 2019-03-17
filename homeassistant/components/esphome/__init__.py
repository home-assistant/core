"""Support for esphome devices."""
import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Callable, Tuple

import attr
import voluptuous as vol

from homeassistant import const
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, \
    EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback, Event, State
import homeassistant.helpers.device_registry as dr
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import template
from homeassistant.helpers.dispatcher import async_dispatcher_connect, \
    async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.template import Template
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

# Import config flow so that it's added to the registry
from .config_flow import EsphomeFlowHandler  # noqa

if TYPE_CHECKING:
    from aioesphomeapi import APIClient, EntityInfo, EntityState, DeviceInfo, \
        ServiceCall, UserService

DOMAIN = 'esphome'
REQUIREMENTS = ['aioesphomeapi==1.7.0']

_LOGGER = logging.getLogger(__name__)

DISPATCHER_UPDATE_ENTITY = 'esphome_{entry_id}_update_{component_key}_{key}'
DISPATCHER_REMOVE_ENTITY = 'esphome_{entry_id}_remove_{component_key}_{key}'
DISPATCHER_ON_LIST = 'esphome_{entry_id}_on_list'
DISPATCHER_ON_DEVICE_UPDATE = 'esphome_{entry_id}_on_device_update'
DISPATCHER_ON_STATE = 'esphome_{entry_id}_on_state'

STORAGE_KEY = 'esphome.{}'
STORAGE_VERSION = 1

# The HA component types this integration supports
HA_COMPONENTS = [
    'binary_sensor',
    'camera',
    'cover',
    'fan',
    'light',
    'sensor',
    'switch',
]

# No config schema - only configuration entry
CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


@attr.s
class RuntimeEntryData:
    """Store runtime data for esphome config entries."""

    entry_id = attr.ib(type=str)
    client = attr.ib(type='APIClient')
    store = attr.ib(type=Store)
    reconnect_task = attr.ib(type=Optional[asyncio.Task], default=None)
    state = attr.ib(type=Dict[str, Dict[str, Any]], factory=dict)
    info = attr.ib(type=Dict[str, Dict[str, Any]], factory=dict)
    services = attr.ib(type=Dict[int, 'UserService'], factory=dict)
    available = attr.ib(type=bool, default=False)
    device_info = attr.ib(type='DeviceInfo', default=None)
    cleanup_callbacks = attr.ib(type=List[Callable[[], None]], factory=list)
    disconnect_callbacks = attr.ib(type=List[Callable[[], None]], factory=list)

    def async_update_entity(self, hass: HomeAssistantType, component_key: str,
                            key: int) -> None:
        """Schedule the update of an entity."""
        signal = DISPATCHER_UPDATE_ENTITY.format(
            entry_id=self.entry_id, component_key=component_key, key=key)
        async_dispatcher_send(hass, signal)

    def async_remove_entity(self, hass: HomeAssistantType, component_key: str,
                            key: int) -> None:
        """Schedule the removal of an entity."""
        signal = DISPATCHER_REMOVE_ENTITY.format(
            entry_id=self.entry_id, component_key=component_key, key=key)
        async_dispatcher_send(hass, signal)

    def async_update_static_infos(self, hass: HomeAssistantType,
                                  infos: 'List[EntityInfo]') -> None:
        """Distribute an update of static infos to all platforms."""
        signal = DISPATCHER_ON_LIST.format(entry_id=self.entry_id)
        async_dispatcher_send(hass, signal, infos)

    def async_update_state(self, hass: HomeAssistantType,
                           state: 'EntityState') -> None:
        """Distribute an update of state information to all platforms."""
        signal = DISPATCHER_ON_STATE.format(entry_id=self.entry_id)
        async_dispatcher_send(hass, signal, state)

    def async_update_device_state(self, hass: HomeAssistantType) -> None:
        """Distribute an update of a core device state like availability."""
        signal = DISPATCHER_ON_DEVICE_UPDATE.format(entry_id=self.entry_id)
        async_dispatcher_send(hass, signal)

    async def async_load_from_store(self) -> Tuple[List['EntityInfo'],
                                                   List['UserService']]:
        """Load the retained data from store and return de-serialized data."""
        # pylint: disable= redefined-outer-name
        from aioesphomeapi import COMPONENT_TYPE_TO_INFO, DeviceInfo, \
            UserService

        restored = await self.store.async_load()
        if restored is None:
            return [], []

        self.device_info = _attr_obj_from_dict(DeviceInfo,
                                               **restored.pop('device_info'))
        infos = []
        for comp_type, restored_infos in restored.items():
            if comp_type not in COMPONENT_TYPE_TO_INFO:
                continue
            for info in restored_infos:
                cls = COMPONENT_TYPE_TO_INFO[comp_type]
                infos.append(_attr_obj_from_dict(cls, **info))
        services = []
        for service in restored.get('services', []):
            services.append(UserService.from_dict(service))
        return infos, services

    async def async_save_to_store(self) -> None:
        """Generate dynamic data to store and save it to the filesystem."""
        store_data = {
            'device_info': attr.asdict(self.device_info),
            'services': []
        }

        for comp_type, infos in self.info.items():
            store_data[comp_type] = [attr.asdict(info)
                                     for info in infos.values()]
        for service in self.services.values():
            store_data['services'].append(service.to_dict())

        await self.store.async_save(store_data)


def _attr_obj_from_dict(cls, **kwargs):
    return cls(**{key: kwargs[key] for key in attr.fields_dict(cls)})


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Stub to allow setting up this component.

    Configuration through YAML is not supported at this time.
    """
    return True


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigEntry) -> bool:
    """Set up the esphome component."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import APIClient, APIConnectionError

    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]

    cli = APIClient(hass.loop, host, port, password,
                    client_info="Home Assistant {}".format(const.__version__))

    # Store client in per-config-entry hass.data
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry.entry_id),
                  encoder=JSONEncoder)
    entry_data = hass.data[DOMAIN][entry.entry_id] = RuntimeEntryData(
        client=cli,
        entry_id=entry.entry_id,
        store=store,
    )

    async def on_stop(event: Event) -> None:
        """Cleanup the socket client on HA stop."""
        await _cleanup_instance(hass, entry)

    entry_data.cleanup_callbacks.append(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_stop)
    )

    @callback
    def async_on_state(state: 'EntityState') -> None:
        """Send dispatcher updates when a new state is received."""
        entry_data.async_update_state(hass, state)

    @callback
    def async_on_service_call(service: 'ServiceCall') -> None:
        """Call service when user automation in ESPHome config is triggered."""
        domain, service_name = service.service.split('.', 1)
        service_data = service.data

        if service.data_template:
            try:
                data_template = {key: Template(value) for key, value in
                                 service.data_template.items()}
                template.attach(hass, data_template)
                service_data.update(template.render_complex(
                    data_template, service.variables))
            except TemplateError as ex:
                _LOGGER.error('Error rendering data template: %s', ex)
                return

        hass.async_create_task(hass.services.async_call(
            domain, service_name, service_data, blocking=True))

    async def send_home_assistant_state(entity_id: str, _,
                                        new_state: Optional[State]) -> None:
        """Forward Home Assistant states to ESPHome."""
        if new_state is None:
            return
        await cli.send_home_assistant_state(entity_id, new_state.state)

    @callback
    def async_on_state_subscription(entity_id: str) -> None:
        """Subscribe and forward states for requested entities."""
        unsub = async_track_state_change(
            hass, entity_id, send_home_assistant_state)
        entry_data.disconnect_callbacks.append(unsub)
        # Send initial state
        hass.async_create_task(send_home_assistant_state(
            entity_id, None, hass.states.get(entity_id)))

    async def on_login() -> None:
        """Subscribe to states and list entities on successful API login."""
        try:
            entry_data.device_info = await cli.device_info()
            entry_data.available = True
            await _async_setup_device_registry(hass, entry,
                                               entry_data.device_info)
            entry_data.async_update_device_state(hass)

            entity_infos, services = await cli.list_entities_services()
            entry_data.async_update_static_infos(hass, entity_infos)
            await _setup_services(hass, entry_data, services)
            await cli.subscribe_states(async_on_state)
            await cli.subscribe_service_calls(async_on_service_call)
            await cli.subscribe_home_assistant_states(
                async_on_state_subscription)

            hass.async_create_task(entry_data.async_save_to_store())
        except APIConnectionError as err:
            _LOGGER.warning("Error getting initial data: %s", err)
            # Re-connection logic will trigger after this
            await cli.disconnect()

    try_connect = await _setup_auto_reconnect_logic(hass, cli, entry, host,
                                                    on_login)

    # This is a bit of a hack: We schedule complete_setup into the
    # event loop and return immediately (return True)
    #
    # Usually, we should avoid that so that HA can track which components
    # have been started successfully and which failed to be set up.
    # That doesn't work here for two reasons:
    #  - We have our own re-connect logic
    #  - Before we do the first try_connect() call, we need to make sure
    #    all dispatcher event listeners have been connected, so
    #    async_forward_entry_setup needs to be awaited. However, if we
    #    would await async_forward_entry_setup() in async_setup_entry(),
    #    we would end up with a deadlock.
    #
    # Solution is: complete the setup outside of the async_setup_entry()
    # function. HA will wait until the first connection attempt is made
    # before starting up (as it should), but if the first connection attempt
    # fails we will schedule all next re-connect attempts outside of the
    # tracked tasks (hass.loop.create_task). This way HA won't stall startup
    # forever until a connection is successful.

    async def complete_setup() -> None:
        """Complete the config entry setup."""
        tasks = []
        for component in HA_COMPONENTS:
            tasks.append(hass.config_entries.async_forward_entry_setup(
                entry, component))
        await asyncio.wait(tasks)

        infos, services = await entry_data.async_load_from_store()
        entry_data.async_update_static_infos(hass, infos)
        await _setup_services(hass, entry_data, services)

        # If first connect fails, the next re-connect will be scheduled
        # outside of _pending_task, in order not to delay HA startup
        # indefinitely
        await try_connect(is_disconnect=False)

    hass.async_create_task(complete_setup())
    return True


async def _setup_auto_reconnect_logic(hass: HomeAssistantType,
                                      cli: 'APIClient',
                                      entry: ConfigEntry, host: str, on_login):
    """Set up the re-connect logic for the API client."""
    from aioesphomeapi import APIConnectionError

    async def try_connect(tries: int = 0, is_disconnect: bool = True) -> None:
        """Try connecting to the API client. Will retry if not successful."""
        if entry.entry_id not in hass.data[DOMAIN]:
            # When removing/disconnecting manually
            return

        data = hass.data[DOMAIN][entry.entry_id]  # type: RuntimeEntryData
        for disconnect_cb in data.disconnect_callbacks:
            disconnect_cb()
        data.disconnect_callbacks = []
        data.available = False
        data.async_update_device_state(hass)

        if is_disconnect:
            # This can happen often depending on WiFi signal strength.
            # So therefore all these connection warnings are logged
            # as infos. The "unavailable" logic will still trigger so the
            # user knows if the device is not connected.
            _LOGGER.info("Disconnected from ESPHome API for %s", host)

        if tries != 0:
            # If not first re-try, wait and print message
            # Cap wait time at 1 minute. This is because while working on the
            # device (e.g. soldering stuff), users don't want to have to wait
            # a long time for their device to show up in HA again (this was
            # mentioned a lot in early feedback)
            #
            # In the future another API will be set up so that the ESP can
            # notify HA of connectivity directly, but for new we'll use a
            # really short reconnect interval.
            tries = min(tries, 10)  # prevent OverflowError
            wait_time = int(round(min(1.8**tries, 60.0)))
            _LOGGER.info("Trying to reconnect in %s seconds", wait_time)
            await asyncio.sleep(wait_time)

        try:
            await cli.connect(on_stop=try_connect, login=True)
        except APIConnectionError as error:
            _LOGGER.info("Can't connect to ESPHome API for %s: %s",
                         host, error)
            # Schedule re-connect in event loop in order not to delay HA
            # startup. First connect is scheduled in tracked tasks.
            data.reconnect_task = hass.loop.create_task(
                try_connect(tries + 1, is_disconnect=False))
        else:
            _LOGGER.info("Successfully connected to %s", host)
            hass.async_create_task(on_login())

    return try_connect


async def _async_setup_device_registry(hass: HomeAssistantType,
                                       entry: ConfigEntry,
                                       device_info: 'DeviceInfo'):
    """Set up device registry feature for a particular config entry."""
    sw_version = device_info.esphome_core_version
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


async def _register_service(hass: HomeAssistantType,
                            entry_data: RuntimeEntryData,
                            service: 'UserService'):
    from aioesphomeapi import USER_SERVICE_ARG_BOOL, USER_SERVICE_ARG_INT, \
        USER_SERVICE_ARG_FLOAT, USER_SERVICE_ARG_STRING
    service_name = '{}_{}'.format(entry_data.device_info.name, service.name)
    schema = {}
    for arg in service.args:
        schema[vol.Required(arg.name)] = {
            USER_SERVICE_ARG_BOOL: cv.boolean,
            USER_SERVICE_ARG_INT: vol.Coerce(int),
            USER_SERVICE_ARG_FLOAT: vol.Coerce(float),
            USER_SERVICE_ARG_STRING: cv.string,
        }[arg.type_]

    async def execute_service(call):
        await entry_data.client.execute_service(service, call.data)

    hass.services.async_register(DOMAIN, service_name, execute_service,
                                 vol.Schema(schema))


async def _setup_services(hass: HomeAssistantType,
                          entry_data: RuntimeEntryData,
                          services: List['UserService']):
    old_services = entry_data.services.copy()
    to_unregister = []
    to_register = []
    for service in services:
        if service.key in old_services:
            # Already exists
            matching = old_services.pop(service.key)
            if matching != service:
                # Need to re-register
                to_unregister.append(matching)
                to_register.append(service)
        else:
            # New service
            to_register.append(service)

    for service in old_services.values():
        to_unregister.append(service)

    entry_data.services = {serv.key: serv for serv in services}

    for service in to_unregister:
        service_name = '{}_{}'.format(entry_data.device_info.name,
                                      service.name)
        hass.services.async_remove(DOMAIN, service_name)

    for service in to_register:
        await _register_service(hass, entry_data, service)


async def _cleanup_instance(hass: HomeAssistantType,
                            entry: ConfigEntry) -> None:
    """Cleanup the esphome client if it exists."""
    data = hass.data[DOMAIN].pop(entry.entry_id)  # type: RuntimeEntryData
    if data.reconnect_task is not None:
        data.reconnect_task.cancel()
    for disconnect_cb in data.disconnect_callbacks:
        disconnect_cb()
    for cleanup_callback in data.cleanup_callbacks:
        cleanup_callback()
    await data.client.disconnect()


async def async_unload_entry(hass: HomeAssistantType,
                             entry: ConfigEntry) -> bool:
    """Unload an esphome config entry."""
    await _cleanup_instance(hass, entry)

    tasks = []
    for component in HA_COMPONENTS:
        tasks.append(hass.config_entries.async_forward_entry_unload(
            entry, component))
    await asyncio.wait(tasks)

    return True


async def platform_async_setup_entry(hass: HomeAssistantType,
                                     entry: ConfigEntry,
                                     async_add_entities,
                                     *,
                                     component_key: str,
                                     info_type,
                                     entity_type,
                                     state_type
                                     ) -> None:
    """Set up an esphome platform.

    This method is in charge of receiving, distributing and storing
    info and state updates.
    """
    entry_data = hass.data[DOMAIN][entry.entry_id]  # type: RuntimeEntryData
    entry_data.info[component_key] = {}
    entry_data.state[component_key] = {}

    @callback
    def async_list_entities(infos: List['EntityInfo']):
        """Update entities of this platform when entities are listed."""
        old_infos = entry_data.info[component_key]
        new_infos = {}
        add_entities = []
        for info in infos:
            if not isinstance(info, info_type):
                # Filter out infos that don't belong to this platform.
                continue

            if info.key in old_infos:
                # Update existing entity
                old_infos.pop(info.key)
            else:
                # Create new entity
                entity = entity_type(entry.entry_id, component_key, info.key)
                add_entities.append(entity)
            new_infos[info.key] = info

        # Remove old entities
        for info in old_infos.values():
            entry_data.async_remove_entity(hass, component_key, info.key)
        entry_data.info[component_key] = new_infos
        async_add_entities(add_entities)

    signal = DISPATCHER_ON_LIST.format(entry_id=entry.entry_id)
    entry_data.cleanup_callbacks.append(
        async_dispatcher_connect(hass, signal, async_list_entities)
    )

    @callback
    def async_entity_state(state: 'EntityState'):
        """Notify the appropriate entity of an updated state."""
        if not isinstance(state, state_type):
            return
        entry_data.state[component_key][state.key] = state
        entry_data.async_update_entity(hass, component_key, state.key)

    signal = DISPATCHER_ON_STATE.format(entry_id=entry.entry_id)
    entry_data.cleanup_callbacks.append(
        async_dispatcher_connect(hass, signal, async_entity_state)
    )


class EsphomeEntity(Entity):
    """Define a generic esphome entity."""

    def __init__(self, entry_id: str, component_key: str, key: int):
        """Initialize."""
        self._entry_id = entry_id
        self._component_key = component_key
        self._key = key
        self._remove_callbacks = []  # type: List[Callable[[], None]]

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        kwargs = {
            'entry_id': self._entry_id,
            'component_key': self._component_key,
            'key': self._key,
        }
        self._remove_callbacks.append(
            async_dispatcher_connect(self.hass,
                                     DISPATCHER_UPDATE_ENTITY.format(**kwargs),
                                     self._on_update)
        )

        self._remove_callbacks.append(
            async_dispatcher_connect(self.hass,
                                     DISPATCHER_REMOVE_ENTITY.format(**kwargs),
                                     self.async_remove)
        )

        self._remove_callbacks.append(
            async_dispatcher_connect(
                self.hass, DISPATCHER_ON_DEVICE_UPDATE.format(**kwargs),
                self.async_schedule_update_ha_state)
        )

    async def _on_update(self):
        """Update the entity state when state or static info changed."""
        self.async_schedule_update_ha_state()

    async def async_will_remove_from_hass(self):
        """Unregister callbacks."""
        for remove_callback in self._remove_callbacks:
            remove_callback()
        self._remove_callbacks = []

    @property
    def _entry_data(self) -> RuntimeEntryData:
        return self.hass.data[DOMAIN][self._entry_id]

    @property
    def _static_info(self) -> 'EntityInfo':
        return self._entry_data.info[self._component_key][self._key]

    @property
    def _device_info(self) -> 'DeviceInfo':
        return self._entry_data.device_info

    @property
    def _client(self) -> 'APIClient':
        return self._entry_data.client

    @property
    def _state(self) -> 'Optional[EntityState]':
        try:
            return self._entry_data.state[self._component_key][self._key]
        except KeyError:
            return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        device = self._device_info

        if device.has_deep_sleep:
            # During deep sleep the ESP will not be connectable (by design)
            # For these cases, show it as available
            return True

        return self._entry_data.available

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique id identifying the entity."""
        if not self._static_info.unique_id:
            return None
        return self._static_info.unique_id

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            'connections': {(dr.CONNECTION_NETWORK_MAC,
                             self._device_info.mac_address)}
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._static_info.name

    @property
    def should_poll(self) -> bool:
        """Disable polling."""
        return False
