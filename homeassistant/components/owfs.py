"""
Connects to the OWFS platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/owfs/
"""

import logging
import asyncio
import anyio
import re

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
CONF_TYPE = 'type'
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

KNOWN_POLL_ITEMS = {'alarm', 'temperature', 'value'}

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_ADDRESS): owfs_address,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TYPE): cv.string,
    vol.Optional(CONF_SCAN): positive_float,
    vol.Optional(CONF_POLL): vol.Schema(
        dict((vol.Optional(k), cv.positive_int) for k in KNOWN_POLL_ITEMS)
    ),
})

async def async_setup(hass, config):
    """Set up the OWFS component."""
    evt = anyio.create_event()

    try:
        hass.data[DATA_OWFS] = mod = OWFSModule(hass, config)
        #hass.data[DATA_OWFS].async_create_exposures()
        await hass.data[DATA_OWFS].start(evt)

    except Exception as ex:
        _LOGGER.exception("Can't connect to OWFS interface: %s", repr(ex))
        hass.components.persistent_notification.async_create(
            "Can't connect to OWFS interface: {0!r}".format(ex),
            title="OWFS")
        return False

    codemap = {
            0x10: 'sensor',
            0x1F: None, # Buses are handled transparently
            0x81: None, # ID chips are skipped
            }

    disc = {} # component: [(device, class)]
    objs = []
    for dev in mod.service.devices:
        t = codemap.get(dev.family, False)
        if t is None:
            _LOGGER.info("Ignored device: %s", repr(dev))
            continue
        elif t is False:
            _LOGGER.warning("Device not handled: %s", repr(dev))
            objs.append(UnknownDevice(hass, dev))
        else:
            d = disc.setdefault(t, [])
            d.append(dev)

    for component, data in disc.items():
        mod.start_run(discovery.async_load_platform,
            hass, component, DOMAIN, {
                ATTR_DEVICES: data,
            }, config)

    hass.services.async_register(
        DOMAIN, SERVICE_OWFS_SEND,
        hass.data[DATA_OWFS].service_set_owfs_value,
        schema=SERVICE_OWFS_SEND_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_OWFS_READ,
        hass.data[DATA_OWFS].service_get_owfs_value,
        schema=SERVICE_OWFS_READ_SCHEMA)

    if objs:
        for obj in objs:
            self._devices[obj.dev.id] = obj
        mod.start_run(async_add_entities, objs)

    hass.async_create_task(mod.start_done())

    return True

async def init_devices(hass, domain, config, discovery_info, async_add_entities, classes):
    mod = hass.data[DATA_OWFS]
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    if config:
        assert not discovery_info, discovery_info
        dev = mod.service.get_device(config[CONF_ADDRESS])
        try:
            cls = classes[dev.family]
        except KeyError:
            cls = UnknownDevice

        obj = cls(hass, dev, config=config)
        mod._add_device(obj)
        async_add_entities((obj,))
        poll = config.get('poll', {})
        for k,v in poll.items():
            await dev.set_polling_interval(k,v)

    else:
        objs = []
        for dev in discovery_info.get('devices', ()):
            reg = entity_registry.async_get_entity_id(domain, DOMAIN, dev.id)
            if reg is not None:
                continue # already known
            try:
                cls = classes[dev.family]
            except KeyError:
                cls = UnknownDevice
            else:
                objs.append(cls(hass, dev))
        if objs:
            for obj in objs:
                mod._add_device(obj)
            async_add_entities(objs)


class OWFSDevice(Entity):
    """Representation of HomeAssistant's OWFS device"""
    def __init__(self, hass: HomeAssistant, dev: OW_Device, config: dict={}):
        self.hass = hass
        self.dev = dev
        name=config.get('name')
        if name is None:
            name = "{} {}".format(self.__class__.__name__, dev.id)
        self._name = name
        self._config = config

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self):
        """overrides this Entity property.
        OWFS doesn't require polling by HASS.
        """
        return False

    @property
    def unique_id(self):
        """overrides this Entity property.
        Return the OWFS device ID (considered unique).
        """
        return self.dev.id

    @property
    def entity_id(self):
        """overrides this Entity property.
        Return the OWFS device ID (considered unique).
        """
        try:
            return self.dev.__entity_id
        except AttributeError:
            return None
    
    @entity_id.setter
    def entity_id(self, value):
        self.dev.__entity_id = value

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
            await self.async_update_ha_state()
            self.hass.bus.async_fire(EVENT_OWFS_VALUE, {
                    SERVICE_OWFS_ADDRESS: evt.device.id,
                    SERVICE_OWFS_ATTRIBUTE: evt.attribute,
                    SERVICE_OWFS_VALUE: evt.value,
                    })


class UnknownDevice(OWFSDevice, Entity):
    """This class represents a device without a specialized handler.
    It is only used for devices that are configured explicitly.
    """
    pass

class OWFSModule:
    """Representation of OWFS connection."""

    def __init__(self, hass, config):
        """Initialize of OWFS module."""
        self.hass = hass
        self.config = config
        self._devices = {}
        self._start_count = 0
        self._start_wait = asyncio.Event()

    async def _start_run(self, proc, args, kwargs):
        try:
            await proc(*args, **kwargs)
        finally:
            self._start_count -= 1
            if not self.start_count:
                self._start_wait.set()

    def start_run(self, proc, *args, **kwargs):
        """Start a setup task"""
        self._start_count += 1
        self.hass.async_create_task(self._start_run, proc, args, kwargs)

    def _add_device(self, obj: OWFSDevice):
        self._devices[obj.dev.id] = obj

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
                _LOGGER.debug("E: {}".format(evt))

                if isinstance(evt, ServerRegistered):
                    n_servers += 1

                elif isinstance(evt, ServerDeregistered):
                    n_servers -= 1
                    if not n_servers:
                        _LOGGER.debug("E: all registered servers gone. Exiting.")
                        return

                elif isinstance(evt, DeviceEvent):
                    dev = self._devices.get(evt.device.id)
                    if dev is None:
                        dev = await self.auto_device(evt.device)
                    if dev is not None:
                        await dev.process_event(evt)

    async def auto_device(self, device: OW_Device):
        _LOGGER.info("Unknown device: {}".format(device))

    async def start(self, ready: Optional[anyio.abc.Event] = None):
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
        if self._start_count > 0:
            await self._start_wait.wait()

        for s in self.config[DOMAIN][CONF_OWFS_SERVER]:
            sd = {'host': s[CONF_HOST]}
            if 'CONF_PORT' in s:
                sd['port'] = s[CONF_PORT]
            if 'CONF_SCAN' in s:
                sd['scan'] = s[CONF_SCAN]
            if 'CONF_SCAN_DELAY' in s:
                sd['initial_scan'] = s[CONF_SCAN_DELAY]
            if 'CONF_POLL' in s:
                sd['polling'] = s[CONF_POLL]
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



