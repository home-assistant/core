"""EBUS Integration."""
import asyncio
import collections
import copy
import logging
from typing import Dict

from pyebus import CircuitMap, Ebus, FieldDef, get_icon

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    API,
    CONF_CIRCUITMAP,
    CONF_MESSAGES,
    CONF_MSGDEFCODES,
    DEFAULT_CIRCUITMAP,
    DOMAIN,
    PRIO,
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

    api.start()

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
        hass.data[DOMAIN].pop(config_entry.entry_id)

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

    def __init__(self, hass: HomeAssistantType):
        """EBUS API."""
        self._hass = hass
        self._data = {}
        self._fieldlistener = collections.defaultdict(list)
        self._ebussetter = None
        self._ebus = None
        self.circuitmap = None
        self._observer = None
        self._tasks = []

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
        self._ebus = ebus
        self._ebussetter = copy.copy(ebus)

        # circuitmap
        circuitmap = entry.data.get(CONF_CIRCUITMAP, {})
        self.circuitmap = CircuitMap(DEFAULT_CIRCUITMAP)
        self.circuitmap.update(circuitmap)

    @property
    def ident(self):
        """Ident."""
        return f"{self._ebus.host}:{self._ebus.port}"

    @property
    def msgdefs(self):
        """Message Definitions."""
        return self._ebus.msgdefs

    def start(self):
        """Start."""
        self._tasks.append(asyncio.create_task(self.async_observe()))

    async def async_stop(self, **kwargs):
        """Stop."""
        asyncio.gather(*[_await_cancel(task) for task in self._tasks])
        self._tasks.clear()

    async def async_observe(self):
        """Observe EBUS."""
        data = self._data
        broken = False
        while True:
            try:
                async for msg in self._ebus.async_observe(
                    setprio=True, defaultprio=PRIO, ttl=TTL
                ):
                    broken = False
                    _LOGGER.info(msg)
                    if msg.valid:
                        for field in msg.fields:
                            data[field.fielddef.ident] = field.value
                            self.notify(field.fielddef)
                    else:
                        # remove outdated values
                        for fielddef in msg.msgdef.fields:
                            data.pop(fielddef.ident, None)
                            self.notify(fielddef)
            except Exception as exc:
                if not broken:
                    _LOGGER.error(exc)
                broken = True
                await asyncio.sleep(60)

    def notify(self, fielddef):
        """Notify about field update."""
        for entity in self._fieldlistener[fielddef.ident]:
            entity.async_write_ha_state()

    async def async_set_field(self, fielddef, value):
        """Set Field."""
        msgdefs = self._ebussetter.msgdefs.resolve([fielddef.ident])
        msgdef = tuple(msgdefs)[0]
        if self._ebussetter:
            await self._ebussetter.async_write(msgdef, value)

    @callback
    def subscribe(self, entity, fielddef):
        """Subscribe an entity from API fetches."""
        self._fieldlistener[fielddef.ident].append(entity)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe an entity from API fetches (when disable)."""
            self._fieldlistener[fielddef.ident].remove(entity)

        return unsubscribe

    def get_state(self, fielddef):
        """Get Field State."""
        return self._data.get(fielddef.ident, None)

    def get_available(self, fielddef):
        """Get Field Available."""
        return fielddef.ident in self._data


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
        return f"{circuit} {msgdef.name} {self._fielddef.name}"

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
            "name": f"EBUS - {circuit}",
        }

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(self._api.subscribe(self, self._fielddef))

    @property
    def device_state_attributes(self):
        """Device State Attributes."""
        return {
            "Identifier": self._fielddef.ident,
            "Writeable": "Yes" if self._fielddef.parent.write else "No",
            "Values": self._fielddef.type_.comment,
        }
