"""
Connects to the OWFS platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/owfs/
"""

import logging
import asyncio
import re
from weakref import WeakValueDictionary
try:
    from time import monotonic as time
except ImportError:
    from time import time

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_ENTITY_ID, CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

from trio_owfs import OWFS
import trio_owfs.service
from trio_owfs.device import Device as OW_Device
from trio_owfs.event import ServerRegistered, ServerConnected, ServerDisconnected, \
    ServerDeregistered, DeviceAdded, DeviceLocated, DeviceNotFound, BusAdded_Path, \
    BusAdded, BusDeleted, DeviceEvent, DeviceAlarm, DeviceValue

from typing import Optional

positive_float = vol.All(vol.Coerce(float), vol.Range(min=0))

REQUIREMENTS = ['trio_owfs>=0.6.7']

DOMAIN = "owfs"
DATA_OWFS = "data_owfs"

EVENT_OWFS_ALARM = "owfs.alarm"
EVENT_OWFS_VALUE = "owfs.value"

CONF_OWFS_SERVER = "server"
CONF_POLL = "poll"
CONF_ADDRESS = 'address'
CONF_ATTRIBUTE = 'attr'
CONF_SCAN = 'scan'
CONF_SCAN_DELAY = 'scan_delay'

DEFAULT_NAME = 'OWFS Sensor'

SERVICE_OWFS_SEND = "write"
SERVICE_OWFS_READ = "read"
SERVICE_OWFS_ADDRESS = "device"
SERVICE_OWFS_ATTRIBUTE = "attr"
SERVICE_OWFS_VALUE = "value"
SERVICE_OWFS_RESULTS = "results"

ATTR_DEVICES = 'devices'

_LOGGER = logging.getLogger(__name__)

SERVER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT): cv.port,
    vol.Optional(CONF_POLL): cv.boolean,
    vol.Optional(CONF_SCAN): positive_float,
    vol.Optional(CONF_SCAN_DELAY): positive_float,
})

CONFIG_SCHEMA = vol.Schema({
  DOMAIN: vol.Schema({
    vol.Required(CONF_OWFS_SERVER):
        vol.All(
            cv.ensure_list,
            [SERVER_SCHEMA]),
        }),
}, extra=vol.ALLOW_EXTRA)

SERVICE_OWFS_SEND_SCHEMA = vol.Schema({
    vol.Required(SERVICE_OWFS_ADDRESS): cv.string,
    vol.Required(SERVICE_OWFS_ATTRIBUTE): cv.string,
    vol.Required(SERVICE_OWFS_VALUE): cv.string,
})

SERVICE_OWFS_READ_SCHEMA = vol.Schema({
    vol.Required(SERVICE_OWFS_ADDRESS): cv.string,
    vol.Required(SERVICE_OWFS_ATTRIBUTE): cv.string,
})

def owfs_address(value):
    """Validate an OWFS address."""
    regex = re.compile(r'[0-9A-Fa-f]{2}\.[0-9A-Fa-f]{12}\.[0-9A-Fa-f]{2}$')
    if not regex.match(value):
        raise vol.Invalid('correct is XX.YYYYYYYYYYYY.ZZ; use "owdir -f f.i.c"')
    return str(value).upper()

KNOWN_POLL_ITEMS = {'alarm', 'temperature', 'voltage', 'attr'}

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_ADDRESS): owfs_address,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ATTRIBUTE): cv.string,
    vol.Optional(CONF_POLL): vol.Schema(
        dict((vol.Optional(k), cv.positive_int) for k in KNOWN_POLL_ITEMS)
    ),
})

# CLASSES in ha.<PLATFORM>.owfs points to the actual classes to be
# used. These use the default attribute and thus must not set '_attr'.
CODEMAP = {
    0x10: 'sensor',
    0x1F: None, # Buses are handled transparently
    0x81: None, # ID chips are skipped
}

async def async_setup(hass, config):
    """Set up the OWFS component."""
    try:
        hass.data[DATA_OWFS] = mod = OWFSModule(hass, config)
        #hass.data[DATA_OWFS].async_create_exposures()
        await hass.data[DATA_OWFS].start()

    except Exception as ex:
        _LOGGER.exception("Can't connect to OWFS interface: %s", repr(ex))
        hass.components.persistent_notification.async_create(
            "Can't connect to OWFS interface: {0!r}".format(ex),
            title="OWFS")
        return False

    hass.services.async_register(
        DOMAIN, SERVICE_OWFS_SEND,
        hass.data[DATA_OWFS].service_set_owfs_value,
        schema=SERVICE_OWFS_SEND_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_OWFS_READ,
        hass.data[DATA_OWFS].service_get_owfs_value,
        schema=SERVICE_OWFS_READ_SCHEMA)

    hass.async_create_task(mod.start_done())

    return True

async def init_devices(hass, domain, config, discovery_info, async_add_entities, classes):
    mod = hass.data[DATA_OWFS]
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    if config:
        assert not discovery_info, discovery_info
        dev = mod.service.get_device(config[CONF_ADDRESS])

        attr = config.get(CONF_ATTRIBUTE)
        if attr is not None:
            cls = UnknownDevice
        else:
            try:
                cls = classes[dev.family]
            except KeyError:
                cls = UnknownDevice

        obj = cls(hass, dev, config=config)
        await obj._init(False)

        poll = config.get(CONF_POLL, {})
        for k,v in poll.items():
            if k == 'attr':
                obj._do_poll = v
            else:
                await dev.set_polling_interval(k,v)

        async_add_entities((obj,))

    else:
        objs = []
        for dev in discovery_info.get('devices', ()):
            try:
                dev._OWFSDevice__objects['_default']
            except (KeyError, AttributeError):
                pass
            else:
                continue

            try:
                cls = classes[dev.family]
            except KeyError:
                cls = UnknownDevice
            obj = cls(hass, dev)
            await obj._init(True)
            objs.append(obj)
        if objs:
            async_add_entities(objs)


class OWFSDevice(Entity):
    """Representation of (an attribute of an) OWFS device"""
    _attr = None
    _val = None
    _do_poll = 0
    _next_poll = 0

    def __init__(self, hass: HomeAssistant, dev: OW_Device, config: dict={}):
        self.hass = hass
        self.dev = dev

        name=config.get(CONF_NAME)
        if name is None:
            name = "{} {}".format(self.__class__.__name__, dev.id)
        self._name = name
        self._config = config

        # save a ref to this device
        try:
            reg = dev.__objects
        except AttributeError:
            dev.__objects = reg = WeakValueDictionary()
        attr=config.get(CONF_ATTRIBUTE)
        if attr is None:
            attr = "_default"
        else:
            self._attr = attr
        reg[attr] = self

    async def _init(self, without_config: bool):
        """Async part of device initialization."""
        pass

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self):
        """overrides this Entity property.
        OWFS doesn't require polling by HASS.
        """
        if not self._do_poll:
            return False
        t = time()
        if self._next_poll > t:
            return False
        self._next_poll = t + self._do_poll
        return True

    @property
    def unique_id(self):
        """overrides this Entity property.
        Return the OWFS device ID (considered unique).
        """
        res = self.dev.id
        if self._attr is not None:
            res += "_" + self._attr.replace('/','_')
        return res

    @property
    def available(self):
        """overrides this Entity property.
        Returns True if the device's bus address is known.
        """
        return self.dev.bus is not None

    def __repr__(self):
        rd = repr(self.dev)[1:]
        if self.name and not self.name.endswith(self.dev.id):
            rd = self.name+' '+rd
        return "<%s:%s>" % (self.__class__.__name__, rd)

    async def process_event(self, evt: DeviceEvent):
        """handle an event from OWFS.

        If the event is an alarm, trigger a message.
        """
        if isinstance(evt, DeviceAlarm):
            self.hass.bus.async_fire(EVENT_OWFS_ALARM, {
                    SERVICE_OWFS_ADDRESS: evt.device.id,
                    SERVICE_OWFS_RESULTS: evt.device.results,
                    })
        elif isinstance(evt, DeviceValue):
            if self._attr is not None and evt.attribute == self._attr:
                await self.async_update_ha_state()
                self._val = evt.value


    async def async_update(self):
        if self.dev.bus is None:
            return
        self._val = await self.dev.attr_get(*self._attr.split('/'))

    @property
    def state(self):
        return self._val


class UnknownDevice(OWFSDevice, Entity):
    """This class represents a device without a specialized handler.
    It is only used for devices that are configured explicitly.
    """
    _do_poll = 300


class OWFSModule:
    """Representation of the connection to OWFS."""

    def __init__(self, hass, config):
        """Initialize of OWFS module."""
        self.hass = hass
        self.config = config

    async def _owfs_service(self, evt_start: asyncio.Event):
        """Hold the OWFS service"""
        try:
            async with OWFS() as service:
                self.service = service
                evt_start.set()
                await self.evt_stop.wait()
        except Exception as exc:
            self.service = exc
            evt_start.set()

    async def _owfs_loop(self):
        """Listen for OWFS events"""
        n_servers = 0
        with self.service.events as eq:
            async for evt in eq:
                try:
                    _LOGGER.debug("E: {}".format(evt))

                    if isinstance(evt, ServerRegistered):
                        n_servers += 1

                    elif isinstance(evt, ServerDeregistered):
                        n_servers -= 1
                        if not n_servers:
                            _LOGGER.debug("E: all registered servers gone. Exiting.")
                            return

                    elif isinstance(evt, DeviceEvent):
                        dev = evt.device
                        try:
                            objs = dev._OWFSDevice__objects.values()
                        except AttributeError:
                            obj = await self.auto_device(evt.device)
                            if obj is not None:
                                objs = [obj]
                            else:
                                objs = ()
                        for obj in objs:
                            await obj.process_event(evt)

                        if isinstance(evt, DeviceValue):
                            self.hass.bus.async_fire(EVENT_OWFS_VALUE, {
                                SERVICE_OWFS_ADDRESS: evt.device.id,
                                SERVICE_OWFS_ATTRIBUTE: evt.attribute,
                                SERVICE_OWFS_VALUE: evt.value,
                                })

                except Exception as exc:
                    _LOGGER.exception("While processing %s", repr(evt))

    async def auto_device(self, dev: OW_Device):
        t = CODEMAP.get(dev.family, False)
        if t is None:
            _LOGGER.info("Ignored device: %s", repr(dev))
            return
        elif t is False:
            _LOGGER.warning("Device not handled: %s", repr(dev))
            obj = UnknownDevice(hass, dev)
            await obj._init(True)
            await async_add_entities([obj])
        else:
            await discovery.async_load_platform(
                    self.hass, t, DOMAIN,
                    { ATTR_DEVICES: [dev] },
                    None,
                )
            return None

        _LOGGER.info("%s device: {}".format(obj))
        return obj

    async def start(self):
        """Start OWFS service. Connect to servers."""
        hass = self.hass
        service = hass.data[DATA_OWFS]

        evt_start = asyncio.Event()
        self.evt_stop = asyncio.Event()
        hass.loop.create_task(self._owfs_service(evt_start))
        await evt_start.wait()
        if isinstance(self.service, Exception):
            raise self.service
        hass.loop.create_task(self._owfs_loop())

        def stop_listen(*args, **kwargs):
            self.evt_stop.set()
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_listen)

    async def start_done(self):
        """Actually start the server connections, and poll"""
        for s in self.config[DOMAIN][CONF_OWFS_SERVER]:
            sd = {'host': s[CONF_HOST]}
            if 'CONF_PORT' in s:
                sd['port'] = s[CONF_PORT]
            if 'CONF_POLL' in s:
                sd['polling'] = s[CONF_POLL]
            if 'CONF_SCAN_DELAY' in s:
                sd['initial_scan'] = s[CONF_SCAN_DELAY]
            if 'CONF_SCAN' in s:
                scan = s[CONF_SCAN]
                if scan == -1:
                    scan = None
                sd['scan'] = scan
            await self.service.add_server(**sd)

    async def stop(self, event):
        """Stop OWFFS service. Disconnect from servers."""
        self.evt_stop.set()

    async def service_set_owfs_value(self, call):
        """Service for setting an arbitrary OWFS device's attribute."""
        dev = self.service.get_device(call.data[SERVICE_OWFS_ADDRESS])
        if dev.bus is None:
            _LOGGER.warning("{} is not available".format(dev))
            return 

        try:
            await dev.attr_set(*call.data[SERVICE_OWFS_ATTRIBUTE].split('/'),
                value=call.data[SERVICE_OWFS_VALUE])
        except Exception as exc:
            logger.exception("Writing OWFS: %s %s %s", dev,id, call.data[SERVICE_OWFS_ATTRIBUTE], call.data[SERVICE_OWFS_VALUE])

    async def service_get_owfs_value(self, call):
        """Service for reading an arbitrary OWFS device's attribute"""
        dev = self.service.get_device(call.data[SERVICE_OWFS_ADDRESS])
        if dev.bus is None:
            _LOGGER.warning("{} is not available".format(dev))
            return 

        try:
            res = await dev.attr_get(*call.data[SERVICE_OWFS_ATTRIBUTE].split('/'))
        except Exception as exc:
            logger.exception("Reading OWFS: %s %s", dev,id, call.data[SERVICE_OWFS_ATTRIBUTE])
        else:
            self.hass.bus.async_fire(EVENT_OWFS_VALUE, {
                    SERVICE_OWFS_ADDRESS: evt.device.id,
                    SERVICE_OWFS_ATTRIBUTE: evt.attribute,
                    SERVICE_OWFS_VALUE: evt.value,
                })



