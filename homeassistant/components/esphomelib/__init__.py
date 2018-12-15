"""Support for esphomelib devices."""
import asyncio
import logging
from typing import Any, List

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, \
    EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, \
    async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

DOMAIN = 'esphomelib'
REQUIREMENTS = ['aioesphomeapi==1.0.0']

# hass.data[<config_entry>]['client']
DATA_CLIENT = 'client'
# hass.data[<config_entry>]['reconnect']
DATA_RECONNECT_TASK = 'reconnect'
# hass.data[<config_entry>]['available']
DATA_AVAILABLE = 'available'
# hass.data[<config_entry>]['device_info']
DATA_DEVICE_INFO = 'device_info'
# hass.data[<config_entry>]['state'][<component_name>][<entity_key>]
DATA_STATE = 'state'
# hass.data[<config_entry>]['info'][<component_name>][<entity_key>]
DATA_INFO = 'info'
DISPATCHER_UPDATE_ENTITY = 'esphomelib_{entry_id}_update_{key}'
DISPATCHER_REMOVE_ENTITY = 'esphomelib_{entry_id}_remove_{key}'
DISPATCHER_ON_LIST = 'esphomelib_{entry_id}_on_list'
DISPATCHER_ON_DEVICE_UPDATE = 'esphomelib_{entry_id}_on_device_update'
DISPATCHER_ON_STATE = 'esphomelib_{entry_id}_on_state'
# The HA component types this integration supports
HA_COMPONENTS = ['sensor']

_LOGGER = logging.getLogger(__name__)

# No config schema - only configuration entry
CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Stub to allow setting up this component.

    Configuration through YAML is not supported at this time.
    """
    return True


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

    # Store client in per-config-entry hass.data
    entry_data = hass.data[DOMAIN][entry.entry_id] = {}
    entry_data[DATA_CLIENT] = cli
    entry_data[DATA_AVAILABLE] = False

    try_connect = await _setup_auto_reconnect_logic(hass, cli, entry, host)

    @callback
    def async_on_state(state):
        """Send dispatcher updates when a new state is received."""
        async_dispatcher_send(
            hass, DISPATCHER_ON_STATE.format(entry_id=entry.entry_id), state)

    async def on_login():
        """Subscribe to states and list entities on successful API login."""
        try:

            entry_data[DATA_DEVICE_INFO] = await cli.device_info()
            entry_data[DATA_AVAILABLE] = True
            signal = DISPATCHER_ON_DEVICE_UPDATE.format(
                entry_id=entry.entry_id)
            async_dispatcher_send(hass, signal)

            entity_infos = await cli.list_entities()
            async_dispatcher_send(
                hass, DISPATCHER_ON_LIST.format(entry_id=entry.entry_id),
                entity_infos)
            await cli.subscribe_states(async_on_state)
        except APIConnectionError as err:
            _LOGGER.warning("Error getting initial data: %s", err)
            # Re-connection logic will trigger after this
            await cli.disconnect()

    cli.on_login = on_login

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

    async def complete_setup():
        """Complete the config entry setup."""
        tasks = []
        for component in HA_COMPONENTS:
            tasks.append(hass.config_entries.async_forward_entry_setup(
                entry, component))
        await asyncio.wait(tasks)

        # If first connect fails, the next re-connect will be scheduled
        # outside of _pending_task, in order not to delay HA startup
        # indefinitely
        await try_connect(is_disconnect=False)

    hass.async_create_task(complete_setup())
    return True


async def _setup_auto_reconnect_logic(hass: HomeAssistantType, cli,
                                      entry: ConfigEntry, host):
    """Set up the re-connect logic for the API client."""
    from aioesphomeapi.client import APIConnectionError

    async def try_connect(tries=0, is_disconnect=True):
        """Try connecting to the API client. Will retry if not successful."""
        if entry.entry_id not in hass.data[DOMAIN]:
            # When removing/disconnecting manually
            return

        hass.data[DOMAIN][entry.entry_id][DATA_AVAILABLE] = False
        signal = DISPATCHER_ON_DEVICE_UPDATE.format(entry_id=entry.entry_id)
        async_dispatcher_send(hass, signal)

        if tries != 0:
            # If not first re-try, wait and print message
            wait_time = min(2**tries, 300)
            _LOGGER.info("Trying to reconnect in %s seconds", wait_time)
            await asyncio.sleep(wait_time)

        if is_disconnect and tries == 0:
            # This can happen often depending on WiFi signal strength.
            # So therefore all these connection warnings are logged
            # as infos. The "unavailable" logic will still trigger so the
            # user knows if the device is not connected.
            _LOGGER.info("Disconnected from API")

        try:
            await cli.connect()
            await cli.login()
        except APIConnectionError as error:
            _LOGGER.info("Can't connect to esphomelib API for '%s' (%s)",
                         host, error)
            # Schedule re-connect in event loop in order not to delay HA
            # startup. First connect is scheduled in tracked tasks.
            hass.data[DOMAIN][entry.entry_id][DATA_RECONNECT_TASK] = \
                hass.loop.create_task(try_connect(tries + 1, is_disconnect))
        else:
            _LOGGER.info("Successfully connected to %s", host)

    cli.on_disconnect = try_connect
    return try_connect


async def _cleanup_instance(hass: HomeAssistantType, entry: ConfigEntry):
    """Cleanup the esphomelib client if it exists."""
    data = hass.data[DOMAIN].pop(entry.entry_id)
    client = data[DATA_CLIENT]
    if DATA_RECONNECT_TASK in data:
        data[DATA_RECONNECT_TASK].cancel()
    await client.stop()


async def async_unload_entry(hass, config_entry) -> bool:
    """Unload an esphomelib config entry."""
    await _cleanup_instance(hass, config_entry)

    tasks = []
    for component in HA_COMPONENTS:
        tasks.append(hass.config_entries.async_forward_entry_unload(
            config_entry, component))
    await asyncio.wait(tasks)

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
    """Set up an esphomelib platform.

    This method is in charge of receiving, distributing and storing
    info and state updates.
    """
    data_info = hass.data[DOMAIN][entry.entry_id].setdefault(
        DATA_INFO, {})
    data_info.setdefault(component_key, {})
    data_state = hass.data[DOMAIN][entry.entry_id].setdefault(
        DATA_STATE, {})
    data_state.setdefault(component_key, {})

    @callback
    def async_list_entities(infos: List[Any]):
        """Update entities of this platform when entities are listed."""
        old_infos = data_info[component_key]
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
            signal = DISPATCHER_REMOVE_ENTITY.format(entry_id=entry.entry_id,
                                                     key=info.key)
            async_dispatcher_send(hass, signal)
        data_info[component_key] = new_infos
        async_add_entities(add_entities)

    signal = DISPATCHER_ON_LIST.format(entry_id=entry.entry_id)
    async_dispatcher_connect(hass, signal, async_list_entities)

    @callback
    def async_entity_state(state):
        """Notify the appropriate entity of an updated state."""
        if not isinstance(state, state_type):
            return
        data_state[component_key][state.key] = state
        async_dispatcher_send(
            hass, DISPATCHER_UPDATE_ENTITY.format(entry_id=entry.entry_id,
                                                  key=state.key))

    signal = DISPATCHER_ON_STATE.format(entry_id=entry.entry_id)
    async_dispatcher_connect(hass, signal, async_entity_state)


class EsphomelibEntity(Entity):
    """Define a generic esphomelib entity."""

    def __init__(self, entry_id, component_key, key):
        """Initialize."""
        self._entry_id = entry_id
        self._component_key = component_key
        self._key = key

    async def async_added_to_hass(self):
        """Register callbacks."""
        signal = DISPATCHER_UPDATE_ENTITY.format(
            entry_id=self._entry_id, key=self._key)
        async_dispatcher_connect(self.hass, signal,
                                 self.async_schedule_update_ha_state)

        signal = DISPATCHER_REMOVE_ENTITY.format(
            entry_id=self._entry_id, key=self._key)
        async_dispatcher_connect(self.hass, signal,
                                 self.async_remove)

        signal = DISPATCHER_ON_DEVICE_UPDATE.format(entry_id=self._entry_id)
        async_dispatcher_connect(self.hass, signal,
                                 self.async_schedule_update_ha_state)

    @property
    def _entry_data(self):
        return self.hass.data[DOMAIN][self._entry_id]

    @property
    def _static_info(self):
        return self._entry_data[DATA_INFO][self._component_key][self._key]

    @property
    def _client(self):
        return self._entry_data[DATA_CLIENT]

    @property
    def _state(self):
        try:
            return self._entry_data[DATA_STATE][self._component_key][self._key]
        except KeyError:
            return None

    @property
    def available(self):
        """Return if the entity is available."""
        device = self._entry_data[DATA_DEVICE_INFO]

        if device.has_deep_sleep:
            # During deep sleep the ESP will not be connectable (by design)
            # For these cases, show it as available
            return True

        return self._entry_data[DATA_AVAILABLE]

    @property
    def unique_id(self):
        """Return a unique id identifying the entity."""
        if not self._static_info.unique_id:
            return None
        return self._static_info.unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._static_info.name

    @property
    def should_poll(self):
        """Disable polling."""
        return False
