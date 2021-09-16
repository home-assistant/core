"""Support for RFXtrx devices."""
import asyncio
import binascii
import copy
import functools
import logging

import RFXtrx as rfxtrxmod
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_EVENT,
    COMMAND_GROUP_LIST,
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_FIRE_EVENT,
    CONF_REMOVE_DEVICE,
    DATA_CLEANUP_CALLBACKS,
    DATA_LISTENER,
    DATA_RFXOBJECT,
    DEVICE_PACKET_TYPE_LIGHTING4,
    EVENT_RFXTRX_EVENT,
    SERVICE_SEND,
)

DOMAIN = "rfxtrx"

DEFAULT_SIGNAL_REPETITIONS = 1

SIGNAL_EVENT = f"{DOMAIN}_event"

_LOGGER = logging.getLogger(__name__)


def _bytearray_string(data):
    val = cv.string(data)
    try:
        return bytearray.fromhex(val)
    except ValueError as err:
        raise vol.Invalid(
            "Data must be a hex string with multiple of two characters"
        ) from err


SERVICE_SEND_SCHEMA = vol.Schema({ATTR_EVENT: _bytearray_string})

PLATFORMS = ["switch", "sensor", "light", "binary_sensor", "cover"]


async def async_setup_entry(hass, entry: config_entries.ConfigEntry):
    """Set up the RFXtrx component."""
    hass.data.setdefault(DOMAIN, {})

    hass.data[DOMAIN][DATA_CLEANUP_CALLBACKS] = []

    try:
        await async_setup_internal(hass, entry)
    except asyncio.TimeoutError:
        # Library currently doesn't support reload
        _LOGGER.error(
            "Connection timeout: failed to receive response from RFXtrx device"
        )
        return False

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry: config_entries.ConfigEntry):
    """Unload RFXtrx component."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    hass.services.async_remove(DOMAIN, SERVICE_SEND)

    for cleanup_callback in hass.data[DOMAIN][DATA_CLEANUP_CALLBACKS]:
        cleanup_callback()

    listener = hass.data[DOMAIN][DATA_LISTENER]
    listener()

    rfx_object = hass.data[DOMAIN][DATA_RFXOBJECT]
    await hass.async_add_executor_job(rfx_object.close_connection)

    hass.data.pop(DOMAIN)

    return True


def _create_rfx(config):
    """Construct a rfx object based on config."""
    if config[CONF_PORT] is not None:
        # If port is set then we create a TCP connection
        rfx = rfxtrxmod.Connect(
            (config[CONF_HOST], config[CONF_PORT]),
            None,
            transport_protocol=rfxtrxmod.PyNetworkTransport,
        )
    else:
        rfx = rfxtrxmod.Connect(config[CONF_DEVICE], None)

    return rfx


def _get_device_lookup(devices):
    """Get a lookup structure for devices."""
    lookup = {}
    for event_code, event_config in devices.items():
        event = get_rfx_object(event_code)
        if event is None:
            continue
        device_id = get_device_id(
            event.device, data_bits=event_config.get(CONF_DATA_BITS)
        )
        lookup[device_id] = event_config
    return lookup


async def async_setup_internal(hass, entry: config_entries.ConfigEntry):
    """Set up the RFXtrx component."""
    config = entry.data

    # Initialize library
    async with async_timeout.timeout(30):
        rfx_object = await hass.async_add_executor_job(_create_rfx, config)

    # Setup some per device config
    devices = _get_device_lookup(config[CONF_DEVICES])

    device_registry: DeviceRegistry = (
        await hass.helpers.device_registry.async_get_registry()
    )

    # Declare the Handle event
    @callback
    def async_handle_receive(event):
        """Handle received messages from RFXtrx gateway."""
        # Log RFXCOM event
        if not event.device.id_string:
            return

        event_data = {
            "packet_type": event.device.packettype,
            "sub_type": event.device.subtype,
            "type_string": event.device.type_string,
            "id_string": event.device.id_string,
            "data": binascii.hexlify(event.data).decode("ASCII"),
            "values": getattr(event, "values", None),
        }

        _LOGGER.debug("Receive RFXCOM event: %s", event_data)

        data_bits = get_device_data_bits(event.device, devices)
        device_id = get_device_id(event.device, data_bits=data_bits)

        if device_id not in devices:
            if config[CONF_AUTOMATIC_ADD]:
                _add_device(event, device_id)
            else:
                return

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, *device_id)},
        )
        if device_entry:
            event_data[ATTR_DEVICE_ID] = device_entry.id

        # Callback to HA registered components.
        hass.helpers.dispatcher.async_dispatcher_send(SIGNAL_EVENT, event, device_id)

        # Signal event to any other listeners
        fire_event = devices.get(device_id, {}).get(CONF_FIRE_EVENT)
        if fire_event:
            hass.bus.async_fire(EVENT_RFXTRX_EVENT, event_data)

    @callback
    def _add_device(event, device_id):
        """Add a device to config entry."""
        config = {}
        config[CONF_DEVICE_ID] = device_id

        data = entry.data.copy()
        data[CONF_DEVICES] = copy.deepcopy(entry.data[CONF_DEVICES])
        event_code = binascii.hexlify(event.data).decode("ASCII")
        data[CONF_DEVICES][event_code] = config
        hass.config_entries.async_update_entry(entry=entry, data=data)
        devices[device_id] = config

    def _shutdown_rfxtrx(event):
        """Close connection with RFXtrx."""
        rfx_object.close_connection()

    listener = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_rfxtrx)

    hass.data[DOMAIN][DATA_LISTENER] = listener
    hass.data[DOMAIN][DATA_RFXOBJECT] = rfx_object

    rfx_object.event_callback = lambda event: hass.add_job(async_handle_receive, event)

    def send(call):
        event = call.data[ATTR_EVENT]
        rfx_object.transport.send(event)

    hass.services.async_register(DOMAIN, SERVICE_SEND, send, schema=SERVICE_SEND_SCHEMA)


def get_rfx_object(packetid):
    """Return the RFXObject with the packetid."""
    try:
        binarypacket = bytearray.fromhex(packetid)
    except ValueError:
        return None

    pkt = rfxtrxmod.lowlevel.parse(binarypacket)
    if pkt is None:
        return None
    if isinstance(pkt, rfxtrxmod.lowlevel.SensorPacket):
        obj = rfxtrxmod.SensorEvent(pkt)
    elif isinstance(pkt, rfxtrxmod.lowlevel.Status):
        obj = rfxtrxmod.StatusEvent(pkt)
    else:
        obj = rfxtrxmod.ControlEvent(pkt)

    obj.data = binarypacket
    return obj


def get_pt2262_deviceid(device_id, nb_data_bits):
    """Extract and return the address bits from a Lighting4/PT2262 packet."""
    if nb_data_bits is None:
        return

    try:
        data = bytearray.fromhex(device_id)
    except ValueError:
        return None
    mask = 0xFF & ~((1 << nb_data_bits) - 1)

    data[len(data) - 1] &= mask

    return binascii.hexlify(data)


def get_pt2262_cmd(device_id, data_bits):
    """Extract and return the data bits from a Lighting4/PT2262 packet."""
    try:
        data = bytearray.fromhex(device_id)
    except ValueError:
        return None

    mask = 0xFF & ((1 << data_bits) - 1)

    return hex(data[-1] & mask)


def get_device_data_bits(device, devices):
    """Deduce data bits for device based on a cache of device bits."""
    data_bits = None
    if device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
        for device_id, entity_config in devices.items():
            bits = entity_config.get(CONF_DATA_BITS)
            if get_device_id(device, bits) == device_id:
                data_bits = bits
                break
    return data_bits


def find_possible_pt2262_device(device_ids, device_id):
    """Look for the device which id matches the given device_id parameter."""
    for dev_id in device_ids:
        if len(dev_id) == len(device_id):
            size = None
            for i, (char1, char2) in enumerate(zip(dev_id, device_id)):
                if char1 != char2:
                    break
                size = i
            if size is not None:
                size = len(dev_id) - size - 1
                _LOGGER.info(
                    "Found possible device %s for %s "
                    "with the following configuration:\n"
                    "data_bits=%d\n"
                    "command_on=0x%s\n"
                    "command_off=0x%s\n",
                    device_id,
                    dev_id,
                    size * 4,
                    dev_id[-size:],
                    device_id[-size:],
                )
                return dev_id
    return None


def get_device_id(device, data_bits=None):
    """Calculate a device id for device."""
    id_string = device.id_string
    if data_bits and device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
        masked_id = get_pt2262_deviceid(id_string, data_bits)
        if masked_id:
            id_string = masked_id.decode("ASCII")

    return (f"{device.packettype:x}", f"{device.subtype:x}", id_string)


def connect_auto_add(hass, entry_data, callback_fun):
    """Connect to dispatcher for automatic add."""
    if entry_data[CONF_AUTOMATIC_ADD]:
        hass.data[DOMAIN][DATA_CLEANUP_CALLBACKS].append(
            hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_EVENT, callback_fun)
        )


class RfxtrxEntity(RestoreEntity):
    """Represents a Rfxtrx device.

    Contains the common logic for Rfxtrx lights and switches.
    """

    def __init__(self, device, device_id, event=None):
        """Initialize the device."""
        self._name = f"{device.type_string} {device.id_string}"
        self._device = device
        self._event = event
        self._device_id = device_id
        self._unique_id = "_".join(x for x in self._device_id)
        # If id_string is 213c7f2:1, the group_id is 213c7f2, and the device will respond to
        # group events regardless of their group indices.
        (self._group_id, _, _) = device.id_string.partition(":")

    async def async_added_to_hass(self):
        """Restore RFXtrx device state (ON/OFF)."""
        if self._event:
            self._apply_event(self._event)

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, self._handle_event
            )
        )

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                f"{DOMAIN}_{CONF_REMOVE_DEVICE}_{self._device_id}",
                functools.partial(self.async_remove, force_remove=True),
            )
        )

    @property
    def should_poll(self):
        """No polling needed for a RFXtrx switch."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if not self._event:
            return None
        return {ATTR_EVENT: "".join(f"{x:02x}" for x in self._event.data)}

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def unique_id(self):
        """Return unique identifier of remote device."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, *self._device_id)},
            "name": f"{self._device.type_string} {self._device.id_string}",
            "model": self._device.type_string,
        }

    def _event_applies(self, event, device_id):
        """Check if event applies to me."""
        if "Command" in event.values and event.values["Command"] in COMMAND_GROUP_LIST:
            (group_id, _, _) = event.device.id_string.partition(":")
            return group_id == self._group_id

        # Otherwise, the event only applies to the matching device.
        return device_id == self._device_id

    def _apply_event(self, event):
        """Apply a received event."""
        self._event = event

    @callback
    def _handle_event(self, event, device_id):
        """Handle a reception of data, overridden by other classes."""


class RfxtrxCommandEntity(RfxtrxEntity):
    """Represents a Rfxtrx device.

    Contains the common logic for Rfxtrx lights and switches.
    """

    def __init__(self, device, device_id, signal_repetitions=1, event=None):
        """Initialzie a switch or light device."""
        super().__init__(device, device_id, event=event)
        self.signal_repetitions = signal_repetitions
        self._state = None

    async def _async_send(self, fun, *args):
        rfx_object = self.hass.data[DOMAIN][DATA_RFXOBJECT]
        for _ in range(self.signal_repetitions):
            await self.hass.async_add_executor_job(fun, rfx_object.transport, *args)
