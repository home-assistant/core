"""EBUS Integration."""
import asyncio
import collections
import copy
import itertools
import logging
from typing import Dict

from pyebus import AUTO, OK, CircuitMap, Ebus, FieldDef, get_icon

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    API,
    CHECKINTERVAL,
    CONF_CIRCUITMAP,
    CONF_MESSAGES,
    CONF_MSGDEFCODES,
    DEFAULT_CIRCUITMAP,
    DOMAIN,
    TTL,
    UNDO_UPDATE_LISTENER,
    UNIT_DEVICE_CLASS_MAP,
)

PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set Up The Ebus Component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set Up A Config Entry."""
    undo_listener = config_entry.add_update_listener(update_listener)
    api = EbusApi(hass)
    api.configure(config_entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        API: api,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    await api.async_start()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, api.async_stop)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload A Config Entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()
    await hass.data[DOMAIN][config_entry.entry_id][API].async_stop()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id, None)

    return unload_ok


async def update_listener(hass, config_entry):
    """Handle Options Update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def _await_cancel(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class EbusApi:
    """EBUS API."""

    def __init__(self, hass: HomeAssistantType, checkinterval=CHECKINTERVAL):
        """EBUS API."""
        self._hass = hass
        self._checkinterval = checkinterval
        self._data = {}
        self._fieldlistener = collections.defaultdict(list)
        self._ebus = None
        self.circuitmap = None
        self._tasks = []
        self._state = None
        self._info = {}

    def configure(self, entry: ConfigEntry):
        """Configure."""
        # ebus
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        messages = entry.data[CONF_MESSAGES]
        msgdefcodes = entry.data[CONF_MSGDEFCODES]
        ebus = Ebus(host, port)
        ebus.msgdefcodes = msgdefcodes
        ebus.decode_msgdefcodes()
        if messages:
            ebus.msgdefs = ebus.msgdefs.resolve(messages)
        ebus.msgdefs.set_defaultprio(AUTO)
        self._ebus = ebus

        # circuitmap
        circuitmap = entry.data.get(CONF_CIRCUITMAP, {})
        self.circuitmap = CircuitMap(DEFAULT_CIRCUITMAP)
        self.circuitmap.update(circuitmap)

    @property
    def ident(self):
        """Ident."""
        return f"{self._ebus.host}:{self._ebus.port}"

    @property
    def state(self):
        """Return Connection State."""
        return self._state

    @property
    def info(self):
        """Bus Info."""
        return self._info

    @property
    def msgdefs(self):
        """Message Definitions."""
        return self._ebus.msgdefs

    async def async_start(self):
        """Start."""
        self._tasks.append(asyncio.create_task(self.async_observe()))

    async def async_stop(self, *_):
        """Stop."""
        self._state = "stopping"
        asyncio.gather(*[_await_cancel(task) for task in self._tasks])
        self._tasks.clear()

    async def async_observe(self):
        """Observe EBUS."""
        ebus = copy.copy(self._ebus)
        task = None
        while True:
            state = await ebus.async_get_state()
            _LOGGER.debug(f"Connection {self.ident}: {state}")
            if self._state != state:
                if state == OK:
                    # Reconnect
                    if self._state:
                        _LOGGER.warning(f"Connecting {self.ident}")
                        self._set_state("scanning")
                        await ebus.async_wait_scancompleted()
                    # start observing
                    self._set_state(state)
                    task = asyncio.create_task(self._async_observe())
                    self._tasks.append(task)
                elif task:
                    # stop observing
                    _LOGGER.warning(f"Connection {self.ident}: {state}")
                    self._set_state(state)
                    await _await_cancel(task)
                    task = None
            await asyncio.sleep(self._checkinterval)

    async def _async_observe(self):
        ebus = copy.copy(self._ebus)
        self._set_info(await ebus.async_get_info())
        try:
            async for msg in ebus.async_observe(ttl=TTL):
                _LOGGER.info(msg)
                self._set_msg(msg)
                if self._state != OK:
                    break
        finally:
            self._state = "error"

    def _set_state(self, state):
        """Notify about field update."""
        self._state = state
        for entity in itertools.chain.from_iterable(self._fieldlistener.values()):
            entity.async_write_ha_state()

    def _set_info(self, info):
        self._info = info
        for entity in self._fieldlistener[None]:
            entity.async_write_ha_state()

    def _set_msg(self, msg):
        data = self._data
        if msg.valid:
            for field in msg.fields:
                data[field.fielddef.ident] = field.value
                self._notify_field(field.fielddef)
        else:
            # remove outdated values
            for fielddef in msg.msgdef.fields:
                data.pop(fielddef.ident, None)
                self._notify_field(fielddef)

    def _notify_field(self, fielddef):
        """Notify about field update."""
        for entity in self._fieldlistener[fielddef.ident]:
            if entity.enabled:
                entity.async_write_ha_state()

    async def async_set_field(self, fielddef, value):
        """Set Field."""
        msgdef = fielddef.msgdef.replace(children=[fielddef])
        if self._ebus:
            await self._ebus.async_write(msgdef, value)

    def get_field_state(self, fielddef):
        """Get Field State."""
        return self._data.get(fielddef.ident, None)

    def is_field_available(self, fielddef):
        """Get Field Available."""
        return self._state == OK and fielddef.ident in self._data

    @callback
    def subscribe(self, entity, fielddef=None):
        """Subscribe an entity from API fetches."""
        ident = fielddef.ident if fielddef else None
        self._fieldlistener[ident].append(entity)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe an entity from API fetches (when disable)."""
            self._fieldlistener[ident].remove(entity)

        return unsubscribe


class EbusEntity(Entity):
    """EBUS Entity."""

    def __init__(self, api: EbusApi, ident: str):
        """EBUS Entity."""
        super().__init__()
        self._api = api
        self._unique_id = f"{api.ident}/{ident}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._api.ident)},
            "name": "EBUS",
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False


class EbusFieldEntity(EbusEntity):
    """EBUS Entity."""

    def __init__(self, api: EbusApi, fielddef: FieldDef):
        """EBUS Entity."""
        super().__init__(api, fielddef.ident)
        self._fielddef = fielddef
        self._device_class = UNIT_DEVICE_CLASS_MAP.get(self._fielddef.unit, None)

    @property
    def name(self) -> str:
        """Return the name."""
        msgdef = self._fielddef.parent
        circuit = self._api.circuitmap.get_humanname(msgdef.circuit)
        if circuit:
            return f"{circuit} {msgdef.name} {self._fielddef.name}"
        else:
            return f"{msgdef.name} {self._fielddef.name}"

    @property
    def icon(self) -> str:
        """Return the icon."""
        return get_icon(self._fielddef)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        return self._fielddef.unit

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return self._device_class

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        msgdef = self._fielddef.parent
        circuit = self._api.circuitmap.get_humanname(msgdef.circuit)
        return {
            "identifiers": {(DOMAIN, self._api.ident, msgdef.circuit)},
            "name": f"EBUS - {circuit}" if circuit else "EBUS",
            "model": msgdef.circuit,
        }

    @property
    def device_state_attributes(self):
        """Device State Attributes."""
        return {
            "Identifier": self._fielddef.ident,
            "Writeable": "Yes" if self._fielddef.parent.write else "No",
            "Values": self._fielddef.type_.comment,
        }
