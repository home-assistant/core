"""Support for esphome devices."""
import asyncio
import logging
import math
from typing import Any, Callable, Dict, List, Optional

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    DeviceInfo,
    EntityInfo,
    EntityState,
    HomeassistantServiceCall,
    UserService,
    UserServiceArgType,
)
import voluptuous as vol

from homeassistant import const
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, State, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

# Import config flow so that it's added to the registry
from .config_flow import EsphomeFlowHandler  # noqa: F401
from .entry_data import DATA_KEY, RuntimeEntryData

DOMAIN = "esphome"
_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

# No config schema - only configuration entry
CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Stub to allow setting up this component.

    Configuration through YAML is not supported at this time.
    """
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up the esphome component."""
    hass.data.setdefault(DATA_KEY, {})

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]

    zeroconf_instance = await zeroconf.async_get_instance(hass)

    cli = APIClient(
        hass.loop,
        host,
        port,
        password,
        client_info=f"Home Assistant {const.__version__}",
        zeroconf_instance=zeroconf_instance,
    )

    # Store client in per-config-entry hass.data
    store = Store(
        hass, STORAGE_VERSION, f"esphome.{entry.entry_id}", encoder=JSONEncoder
    )
    entry_data = hass.data[DATA_KEY][entry.entry_id] = RuntimeEntryData(
        client=cli, entry_id=entry.entry_id, store=store
    )

    async def on_stop(event: Event) -> None:
        """Cleanup the socket client on HA stop."""
        await _cleanup_instance(hass, entry)

    # Use async_listen instead of async_listen_once so that we don't deregister
    # the callback twice when shutting down Home Assistant.
    # "Unable to remove unknown listener <function EventBus.async_listen_once.<locals>.onetime_listener>"
    entry_data.cleanup_callbacks.append(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_stop)
    )

    @callback
    def async_on_state(state: EntityState) -> None:
        """Send dispatcher updates when a new state is received."""
        entry_data.async_update_state(hass, state)

    @callback
    def async_on_service_call(service: HomeassistantServiceCall) -> None:
        """Call service when user automation in ESPHome config is triggered."""
        domain, service_name = service.service.split(".", 1)
        service_data = service.data

        if service.data_template:
            try:
                data_template = {
                    key: Template(value) for key, value in service.data_template.items()
                }
                template.attach(hass, data_template)
                service_data.update(
                    template.render_complex(data_template, service.variables)
                )
            except TemplateError as ex:
                _LOGGER.error("Error rendering data template for %s: %s", host, ex)
                return

        if service.is_event:
            # ESPHome uses servicecall packet for both events and service calls
            # Ensure the user can only send events of form 'esphome.xyz'
            if domain != "esphome":
                _LOGGER.error(
                    "Can only generate events under esphome domain! (%s)", host
                )
                return
            hass.bus.async_fire(service.service, service_data)
        else:
            hass.async_create_task(
                hass.services.async_call(
                    domain, service_name, service_data, blocking=True
                )
            )

    async def send_home_assistant_state_event(event: Event) -> None:
        """Forward Home Assistant states updates to ESPHome."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        entity_id = event.data.get("entity_id")
        await cli.send_home_assistant_state(entity_id, new_state.state)

    async def _send_home_assistant_state(
        entity_id: str, new_state: Optional[State]
    ) -> None:
        """Forward Home Assistant states to ESPHome."""
        await cli.send_home_assistant_state(entity_id, new_state.state)

    @callback
    def async_on_state_subscription(entity_id: str) -> None:
        """Subscribe and forward states for requested entities."""
        unsub = async_track_state_change_event(
            hass, [entity_id], send_home_assistant_state_event
        )
        entry_data.disconnect_callbacks.append(unsub)
        new_state = hass.states.get(entity_id)
        if new_state is None:
            return
        # Send initial state
        hass.async_create_task(_send_home_assistant_state(entity_id, new_state))

    async def on_login() -> None:
        """Subscribe to states and list entities on successful API login."""
        try:
            entry_data.device_info = await cli.device_info()
            entry_data.available = True
            await _async_setup_device_registry(hass, entry, entry_data.device_info)
            entry_data.async_update_device_state(hass)

            entity_infos, services = await cli.list_entities_services()
            await entry_data.async_update_static_infos(hass, entry, entity_infos)
            await _setup_services(hass, entry_data, services)
            await cli.subscribe_states(async_on_state)
            await cli.subscribe_service_calls(async_on_service_call)
            await cli.subscribe_home_assistant_states(async_on_state_subscription)

            hass.async_create_task(entry_data.async_save_to_store())
        except APIConnectionError as err:
            _LOGGER.warning("Error getting initial data for %s: %s", host, err)
            # Re-connection logic will trigger after this
            await cli.disconnect()

    try_connect = await _setup_auto_reconnect_logic(hass, cli, entry, host, on_login)

    async def complete_setup() -> None:
        """Complete the config entry setup."""
        infos, services = await entry_data.async_load_from_store()
        await entry_data.async_update_static_infos(hass, entry, infos)
        await _setup_services(hass, entry_data, services)

        # Create connection attempt outside of HA's tracked task in order
        # not to delay startup.
        hass.loop.create_task(try_connect(is_disconnect=False))

    hass.async_create_task(complete_setup())
    return True


async def _setup_auto_reconnect_logic(
    hass: HomeAssistantType, cli: APIClient, entry: ConfigEntry, host: str, on_login
):
    """Set up the re-connect logic for the API client."""

    async def try_connect(tries: int = 0, is_disconnect: bool = True) -> None:
        """Try connecting to the API client. Will retry if not successful."""
        if entry.entry_id not in hass.data[DOMAIN]:
            # When removing/disconnecting manually
            return

        data: RuntimeEntryData = hass.data[DOMAIN][entry.entry_id]
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
            wait_time = int(round(min(1.8 ** tries, 60.0)))
            _LOGGER.info("Trying to reconnect to %s in %s seconds", host, wait_time)
            await asyncio.sleep(wait_time)

        try:
            await cli.connect(on_stop=try_connect, login=True)
        except APIConnectionError as error:
            _LOGGER.info("Can't connect to ESPHome API for %s: %s", host, error)
            # Schedule re-connect in event loop in order not to delay HA
            # startup. First connect is scheduled in tracked tasks.
            data.reconnect_task = hass.loop.create_task(
                try_connect(tries + 1, is_disconnect=False)
            )
        else:
            _LOGGER.info("Successfully connected to %s", host)
            hass.async_create_task(on_login())

    return try_connect


async def _async_setup_device_registry(
    hass: HomeAssistantType, entry: ConfigEntry, device_info: DeviceInfo
):
    """Set up device registry feature for a particular config entry."""
    sw_version = device_info.esphome_version
    if device_info.compilation_time:
        sw_version += f" ({device_info.compilation_time})"
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)},
        name=device_info.name,
        manufacturer="espressif",
        model=device_info.model,
        sw_version=sw_version,
    )


async def _register_service(
    hass: HomeAssistantType, entry_data: RuntimeEntryData, service: UserService
):
    service_name = f"{entry_data.device_info.name}_{service.name}"
    schema = {}
    for arg in service.args:
        schema[vol.Required(arg.name)] = {
            UserServiceArgType.BOOL: cv.boolean,
            UserServiceArgType.INT: vol.Coerce(int),
            UserServiceArgType.FLOAT: vol.Coerce(float),
            UserServiceArgType.STRING: cv.string,
            UserServiceArgType.BOOL_ARRAY: [cv.boolean],
            UserServiceArgType.INT_ARRAY: [vol.Coerce(int)],
            UserServiceArgType.FLOAT_ARRAY: [vol.Coerce(float)],
            UserServiceArgType.STRING_ARRAY: [cv.string],
        }[arg.type_]

    async def execute_service(call):
        await entry_data.client.execute_service(service, call.data)

    hass.services.async_register(
        DOMAIN, service_name, execute_service, vol.Schema(schema)
    )


async def _setup_services(
    hass: HomeAssistantType, entry_data: RuntimeEntryData, services: List[UserService]
):
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
        service_name = f"{entry_data.device_info.name}_{service.name}"
        hass.services.async_remove(DOMAIN, service_name)

    for service in to_register:
        await _register_service(hass, entry_data, service)


async def _cleanup_instance(
    hass: HomeAssistantType, entry: ConfigEntry
) -> RuntimeEntryData:
    """Cleanup the esphome client if it exists."""
    data: RuntimeEntryData = hass.data[DATA_KEY].pop(entry.entry_id)
    if data.reconnect_task is not None:
        data.reconnect_task.cancel()
    for disconnect_cb in data.disconnect_callbacks:
        disconnect_cb()
    for cleanup_callback in data.cleanup_callbacks:
        cleanup_callback()
    await data.client.disconnect()
    return data


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload an esphome config entry."""
    entry_data = await _cleanup_instance(hass, entry)
    tasks = []
    for platform in entry_data.loaded_platforms:
        tasks.append(hass.config_entries.async_forward_entry_unload(entry, platform))
    if tasks:
        await asyncio.wait(tasks)
    return True


async def platform_async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities,
    *,
    component_key: str,
    info_type,
    entity_type,
    state_type,
) -> None:
    """Set up an esphome platform.

    This method is in charge of receiving, distributing and storing
    info and state updates.
    """
    entry_data: RuntimeEntryData = hass.data[DOMAIN][entry.entry_id]
    entry_data.info[component_key] = {}
    entry_data.old_info[component_key] = {}
    entry_data.state[component_key] = {}

    @callback
    def async_list_entities(infos: List[EntityInfo]):
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

        # First copy the now-old info into the backup object
        entry_data.old_info[component_key] = entry_data.info[component_key]
        # Then update the actual info
        entry_data.info[component_key] = new_infos

        # Add entities to Home Assistant
        async_add_entities(add_entities)

    signal = f"esphome_{entry.entry_id}_on_list"
    entry_data.cleanup_callbacks.append(
        async_dispatcher_connect(hass, signal, async_list_entities)
    )

    @callback
    def async_entity_state(state: EntityState):
        """Notify the appropriate entity of an updated state."""
        if not isinstance(state, state_type):
            return
        entry_data.state[component_key][state.key] = state
        entry_data.async_update_entity(hass, component_key, state.key)

    signal = f"esphome_{entry.entry_id}_on_state"
    entry_data.cleanup_callbacks.append(
        async_dispatcher_connect(hass, signal, async_entity_state)
    )


def esphome_state_property(func):
    """Wrap a state property of an esphome entity.

    This checks if the state object in the entity is set, and
    prevents writing NAN values to the Home Assistant state machine.
    """

    @property
    def _wrapper(self):
        if self._state is None:
            return None
        val = func(self)
        if isinstance(val, float) and math.isnan(val):
            # Home Assistant doesn't use NAN values in state machine
            # (not JSON serializable)
            return None
        return val

    return _wrapper


class EsphomeEnumMapper:
    """Helper class to convert between hass and esphome enum values."""

    def __init__(self, func: Callable[[], Dict[int, str]]):
        """Construct a EsphomeEnumMapper."""
        self._func = func

    def from_esphome(self, value: int) -> str:
        """Convert from an esphome int representation to a hass string."""
        return self._func()[value]

    def from_hass(self, value: str) -> int:
        """Convert from a hass string to a esphome int representation."""
        inverse = {v: k for k, v in self._func().items()}
        return inverse[value]


def esphome_map_enum(func: Callable[[], Dict[int, str]]):
    """Map esphome int enum values to hass string constants.

    This class has to be used as a decorator. This ensures the aioesphomeapi
    import is only happening at runtime.
    """
    return EsphomeEnumMapper(func)


class EsphomeEntity(Entity):
    """Define a generic esphome entity."""

    def __init__(self, entry_id: str, component_key: str, key: int):
        """Initialize."""
        self._entry_id = entry_id
        self._component_key = component_key
        self._key = key
        self._remove_callbacks: List[Callable[[], None]] = []

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        kwargs = {
            "entry_id": self._entry_id,
            "component_key": self._component_key,
            "key": self._key,
        }
        self._remove_callbacks.append(
            async_dispatcher_connect(
                self.hass,
                (
                    f"esphome_{kwargs.get('entry_id')}"
                    f"_update_{kwargs.get('component_key')}_{kwargs.get('key')}"
                ),
                self._on_state_update,
            )
        )

        self._remove_callbacks.append(
            async_dispatcher_connect(
                self.hass,
                (
                    f"esphome_{kwargs.get('entry_id')}_remove_"
                    f"{kwargs.get('component_key')}_{kwargs.get('key')}"
                ),
                self.async_remove,
            )
        )

        self._remove_callbacks.append(
            async_dispatcher_connect(
                self.hass,
                f"esphome_{kwargs.get('entry_id')}_on_device_update",
                self._on_device_update,
            )
        )

    async def _on_state_update(self) -> None:
        """Update the entity state when state or static info changed."""
        self.async_write_ha_state()

    async def _on_device_update(self) -> None:
        """Update the entity state when device info has changed."""
        if self._entry_data.available:
            # Don't update the HA state yet when the device comes online.
            # Only update the HA state when the full state arrives
            # through the next entity state packet.
            return
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        for remove_callback in self._remove_callbacks:
            remove_callback()
        self._remove_callbacks = []

    @property
    def _entry_data(self) -> RuntimeEntryData:
        return self.hass.data[DATA_KEY][self._entry_id]

    @property
    def _static_info(self) -> EntityInfo:
        # Check if value is in info database. Use a single lookup.
        info = self._entry_data.info[self._component_key].get(self._key)
        if info is not None:
            return info
        # This entity is in the removal project and has been removed from .info
        # already, look in old_info
        return self._entry_data.old_info[self._component_key].get(self._key)

    @property
    def _device_info(self) -> DeviceInfo:
        return self._entry_data.device_info

    @property
    def _client(self) -> APIClient:
        return self._entry_data.client

    @property
    def _state(self) -> Optional[EntityState]:
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
    def device_info(self) -> Dict[str, Any]:
        """Return device registry information for this entity."""
        return {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._device_info.mac_address)}
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._static_info.name

    @property
    def should_poll(self) -> bool:
        """Disable polling."""
        return False
