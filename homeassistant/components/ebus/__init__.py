"""EBUS Integration."""
import asyncio
import collections
import copy
import itertools
import logging
from typing import Dict

from pyebus import (
    NA,
    OK,
    CircuitInfo,
    CircuitMap,
    CommandError,
    Ebus,
    FieldDef,
    Prioritizer,
    get_icon,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    API,
    CHECKINTERVAL,
    CONF_CIRCUITINFOS,
    CONF_MSGDEFCODES,
    DEFAULT_CIRCUITMAP,
    DEFAULT_PRIO,
    DOMAIN,
    PRIO_OFF,
    PRIO_TIMEDELTAS,
    SCAN,
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
    api = Api(hass)
    api.configure(config_entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        API: api,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    await api.monitor.async_start()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, api.monitor.async_stop)

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
    await hass.data[DOMAIN][config_entry.entry_id][API].monitor.async_stop()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id, None)

    return unload_ok


async def update_listener(hass, config_entry):
    """Handle Options Update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class Api:
    """API."""

    def __init__(self, hass: HomeAssistantType, checkinterval=CHECKINTERVAL):
        """EBUS API."""
        self._hass = hass
        self._checkinterval = checkinterval
        self._ebus = None
        self._monitor = None
        self.circuitmap = None
        self._circuitinfos = {}

    def configure(self, entry: ConfigEntry):
        """Configure."""
        # ebus
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        self._ebus = ebus = Ebus(host, port)
        ebus.circuitinfos = tuple(
            CircuitInfo(**circuitinfo) for circuitinfo in entry.data[CONF_CIRCUITINFOS]
        )
        ebus.msgdefcodes = entry.data[CONF_MSGDEFCODES]
        ebus.decode_msgdefcodes()
        self._monitor = Monitor(copy.copy(ebus), self._checkinterval)
        self._circuitinfos = {
            circuitinfo.circuit: circuitinfo for circuitinfo in ebus.circuitinfos
        }
        # circuitmap
        self.circuitmap = CircuitMap(DEFAULT_CIRCUITMAP)

    @property
    def ident(self):
        """Ident."""
        return self._ebus.ident

    @property
    def ebus(self):
        """EBUS."""
        return self._ebus

    @property
    def monitor(self):
        """Monitor."""
        return self._monitor

    async def async_set_field(self, fielddef, value):
        """Set Field."""
        msgdef = fielddef.msgdef.replace(children=[fielddef])
        if self._ebus:
            await self._ebus.async_write(msgdef, value)

    @callback
    def subscribe(self, entity, fielddef=None):
        """Subscribe an entity from API fetches."""
        self._monitor.attach(entity, fielddef=fielddef)

        @callback
        def unsubscribe() -> None:
            """Unsubscribe an entity from API fetches (when disable)."""
            self._monitor.detach(entity, fielddef=fielddef)

        return unsubscribe


class Monitor:
    """EBUS Monitor."""

    def __init__(self, ebus, checkinterval):
        """EBUS Monitor."""
        self._ebus = ebus
        self._checkinterval = checkinterval
        self._data = {}
        self._msglistener = collections.defaultdict(list)
        self._prioritizer = Prioritizer(ebus.msgdefs, PRIO_TIMEDELTAS)
        self._polledmsgs = set()
        self._state = None
        self._info = None
        self._tasks = []

    def get_prio(self, fielddef):
        """Return Corresponding Message Priority."""
        return self._prioritizer.get_prio(fielddef.msgdef)

    @property
    def state(self):
        """Return Connection State."""
        return self._state

    @property
    def info(self):
        """Bus Info."""
        return self._info

    async def async_start(self):
        """Start."""
        self._tasks.append(asyncio.create_task(self._async_main()))

    async def async_stop(self, *_):
        """Stop."""
        self._state = "stopping"
        asyncio.gather(*[self._await_cancel(task) for task in self._tasks])
        self._tasks.clear()

    def attach(self, entity, fielddef=None):
        """Attach an entity to updates."""
        ident = fielddef and fielddef.msgdef.ident
        listeners = self._msglistener[ident]
        listeners.append(entity)
        _LOGGER.debug("attach: %s %s listeners=%d", ident, entity, len(listeners))

    def detach(self, entity, fielddef=None):
        """Attach an entity to updates."""
        ident = fielddef and fielddef.msgdef.ident
        listeners = self._msglistener[ident]
        listeners.remove(entity)
        _LOGGER.debug("detach: %s %s listeners=%d", ident, entity, len(listeners))

    async def _async_main(self):
        """Observe EBUS."""
        ebus = self._ebus
        listenebus = copy.copy(ebus)
        prioebus = copy.copy(ebus)
        localtasks = []
        while True:
            state = await ebus.async_get_state()
            _LOGGER.debug("Connection %s: %s", self._ebus.ident, state)
            # check state
            if self._state != state:
                if state == OK:
                    # Reconnect
                    if self._state:
                        _LOGGER.warning("Reconnecting %s", ebus.ident)
                    self._set_state(SCAN)
                    try:
                        await ebus.async_wait_scancompleted()
                    except (ConnectionError, CommandError):
                        self._set_state("error")
                    else:
                        # Start
                        self._set_state(state)
                        localtasks = [
                            asyncio.create_task(self._async_listen(listenebus)),
                            asyncio.create_task(self._async_prioritize(prioebus)),
                        ]
                        self._tasks += localtasks
                elif localtasks:
                    # Stop
                    _LOGGER.warning("Connection %s: %s", ebus.ident, state or "broken")
                    self._set_state(state)
                    for localtask in localtasks:
                        await self._await_cancel(localtask)
                        self._tasks.remove(localtask)
                    localtasks.clear()
                else:
                    self._set_state(state)
            await asyncio.sleep(self._checkinterval)

    async def _async_listen(self, ebus):
        try:
            async for msg in ebus.async_listen():
                _LOGGER.debug("Listened %s", msg)
                self._set_msg(msg)
                if self._state != OK:
                    break
        except (ConnectionError, CommandError) as exc:
            _LOGGER.info("Observer stopped: %s", exc)
        finally:
            self._set_state("error")

    async def _async_prioritize(self, ebus):
        try:
            while True:
                # Enable/Disable Listening
                listened = {
                    ident
                    for ident, listener in self._msglistener.items()
                    if ident and listener
                }
                for ident in listened - self._polledmsgs:
                    await self._enable_polling(ebus, ident)
                for ident in self._polledmsgs - listened:
                    await self._disable_polling(ebus, ident)
                # Prioritize depending on update rate
                for msgdef in self._prioritizer.iter_priochanges():
                    if msgdef.ident in listened:
                        _LOGGER.info(
                            "Setting %s prio to %d", msgdef.ident, msgdef.setprio
                        )
                        self._set_msg(await ebus.async_read(msgdef, ttl=TTL))
                # Info
                self._set_info(await ebus.async_get_info())
                # Wait
                await asyncio.sleep(self._checkinterval)
        except (ConnectionError, CommandError) as exc:
            _LOGGER.info("Prioritizer stopped: %s", exc)
        finally:
            self._set_state("error")

    async def _enable_polling(self, ebus, ident):
        msgdef = ebus.msgdefs.get_ident(ident)
        if self._state == OK and msgdef.read:
            msg = await ebus.async_read(msgdef, ttl=TTL)
            _LOGGER.debug("Read %s", msg)
            if msg.valid:
                msgdef = msgdef.replace(setprio=DEFAULT_PRIO)
                msg = await ebus.async_read(msgdef, ttl=TTL)
                _LOGGER.info("Enabling polling %s", msgdef.ident)
            else:
                _LOGGER.warning("Skip polling %s", msg)
            self._set_msg(msg)
            self._polledmsgs.add(ident)

    async def _disable_polling(self, ebus, ident):
        msgdef = ebus.msgdefs.get_ident(ident)
        if self._state == OK and msgdef.read:
            _LOGGER.info("Disabling polling %s", msgdef.ident)
            msgdef = msgdef.replace(setprio=PRIO_OFF)
            await ebus.async_read(msgdef, ttl=TTL)
            self._polledmsgs.discard(ident)

    def _set_state(self, state):
        """Notify about field update."""
        self._state = state
        if state != OK:
            # ebusd restart, requires reset
            self._prioritizer.clear()
            self._polledmsgs.clear()
        if state not in (None, SCAN):  # do not propagate broken values, during restart
            self._notify(itertools.chain.from_iterable(self._msglistener.values()))
        else:
            self._notify(self._msglistener[None])

    def _set_info(self, info):
        self._info = info
        self._notify(self._msglistener[None])

    def _set_msg(self, msg):
        data = self._data
        if msg.valid:
            for field in msg.fields:
                data[field.fielddef.ident] = field.value
            self._prioritizer.notify(msg)
        else:
            # remove outdated values
            for fielddef in msg.msgdef.fields:
                data.pop(fielddef.ident, None)
        self._notify(self._msglistener[msg.msgdef.ident])

    @staticmethod
    def _notify(entities):
        for entity in entities:
            if entity.enabled:
                entity.async_write_ha_state()

    def get_field_state(self, fielddef):
        """Get Field State."""
        return self._data.get(fielddef.ident, NA)

    def is_field_available(self, fielddef):
        """Get Field Available."""
        return self._state == OK and self._data.get(fielddef.ident, NA) != NA

    @staticmethod
    async def _await_cancel(task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class EbusEntity(Entity):
    """EBUS Entity."""

    def __init__(self, api: Api, ident: str):
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
            "manufacturer": "EBUSD",
            "model": "EBUSD",
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False


class EbusFieldEntity(EbusEntity):
    """EBUS Entity."""

    def __init__(self, api: Api, fielddef: FieldDef):
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
            name = f"{circuit} {msgdef.name} {self._fielddef.name}"
        else:
            name = f"{msgdef.name} {self._fielddef.name}"
        return name

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
        circuitname = self._api.circuitmap.get_humanname(msgdef.circuit)
        circuitinfo = self._api.ebus.get_circuitinfo(msgdef.circuit)
        info = {
            "identifiers": {(DOMAIN, self._api.ident, msgdef.circuit)},
            "name": f"EBUS - {circuitname}" if circuitname else "EBUS",
            "via_device": (DOMAIN, self._api.ident),
        }
        if circuitinfo:
            info["manufacturer"] = circuitinfo.manufacturer
            info["model"] = circuitinfo.model
            info["sw_version"] = circuitinfo.swversion
        return info

    @property
    def device_state_attributes(self):
        """Device State Attributes."""
        fielddef = self._fielddef
        return {
            "EBUS Identifier": fielddef.ident,
            "Poll Priority": self._api.monitor.get_prio(fielddef),
            "Writeable": "Yes" if fielddef.parent.write else "No",
            "Values": fielddef.type_.comment,
        }
