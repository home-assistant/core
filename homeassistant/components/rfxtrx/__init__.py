"""Support for RFXtrx devices."""
import binascii
from collections import OrderedDict
import logging

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_DEVICES,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    POWER_WATT,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
    UV_INDEX,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_EVENT,
    DATA_RFXTRX_CONFIG,
    DEVICE_PACKET_TYPE_LIGHTING4,
    EVENT_RFXTRX_EVENT,
    SERVICE_SEND,
)

DOMAIN = "rfxtrx"

DEFAULT_SIGNAL_REPETITIONS = 1

CONF_FIRE_EVENT = "fire_event"
CONF_DATA_BITS = "data_bits"
CONF_AUTOMATIC_ADD = "automatic_add"
CONF_SIGNAL_REPETITIONS = "signal_repetitions"
CONF_DEBUG = "debug"
CONF_OFF_DELAY = "off_delay"
SIGNAL_EVENT = f"{DOMAIN}_event"

DATA_TYPES = OrderedDict(
    [
        ("Temperature", TEMP_CELSIUS),
        ("Temperature2", TEMP_CELSIUS),
        ("Humidity", UNIT_PERCENTAGE),
        ("Barometer", ""),
        ("Wind direction", ""),
        ("Rain rate", ""),
        ("Energy usage", POWER_WATT),
        ("Total usage", POWER_WATT),
        ("Sound", ""),
        ("Sensor Status", ""),
        ("Counter value", ""),
        ("UV", UV_INDEX),
        ("Humidity status", ""),
        ("Forecast", ""),
        ("Forecast numeric", ""),
        ("Rain total", ""),
        ("Wind average speed", ""),
        ("Wind gust", ""),
        ("Chill", ""),
        ("Total usage", ""),
        ("Count", ""),
        ("Current Ch. 1", ""),
        ("Current Ch. 2", ""),
        ("Current Ch. 3", ""),
        ("Energy usage", ""),
        ("Voltage", ""),
        ("Current", ""),
        ("Battery numeric", UNIT_PERCENTAGE),
        ("Rssi numeric", "dBm"),
    ]
)

_LOGGER = logging.getLogger(__name__)
DATA_RFXOBJECT = "rfxobject"


def _bytearray_string(data):
    val = cv.string(data)
    try:
        return bytearray.fromhex(val)
    except ValueError:
        raise vol.Invalid("Data must be a hex string with multiple of two characters")


def _ensure_device(value):
    if value is None:
        return DEVICE_DATA_SCHEMA({})
    return DEVICE_DATA_SCHEMA(value)


SERVICE_SEND_SCHEMA = vol.Schema({ATTR_EVENT: _bytearray_string})

DEVICE_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
        vol.Optional(CONF_OFF_DELAY): vol.Any(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_DATA_BITS): cv.positive_int,
        vol.Optional(CONF_COMMAND_ON): cv.byte,
        vol.Optional(CONF_COMMAND_OFF): cv.byte,
        vol.Optional(CONF_SIGNAL_REPETITIONS, default=1): cv.positive_int,
    }
)

BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
        vol.Optional(CONF_DEVICES, default={}): {cv.string: _ensure_device},
    }
)

DEVICE_SCHEMA = BASE_SCHEMA.extend({vol.Required(CONF_DEVICE): cv.string})

PORT_SCHEMA = BASE_SCHEMA.extend(
    {vol.Required(CONF_PORT): cv.port, vol.Optional(CONF_HOST): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(DEVICE_SCHEMA, PORT_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up the RFXtrx component."""
    if DOMAIN not in config:
        hass.data[DATA_RFXTRX_CONFIG] = BASE_SCHEMA({})
        return True

    hass.data[DATA_RFXTRX_CONFIG] = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: config[DOMAIN].get(CONF_HOST),
                CONF_PORT: config[DOMAIN].get(CONF_PORT),
                CONF_DEVICE: config[DOMAIN].get(CONF_DEVICE),
                CONF_DEBUG: config[DOMAIN][CONF_DEBUG],
            },
        )
    )
    return True


async def async_setup_entry(hass, entry: config_entries.ConfigEntry):
    """Set up the RFXtrx component."""
    await hass.async_add_executor_job(setup_internal, hass, entry.data)

    for domain in ["switch", "sensor", "light", "binary_sensor", "cover"]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, domain)
        )

    return True


def setup_internal(hass, config):
    """Set up the RFXtrx component."""

    # Setup some per device config
    device_events = set()
    device_bits = {}
    for event_code, event_config in hass.data[DATA_RFXTRX_CONFIG][CONF_DEVICES].items():
        event = get_rfx_object(event_code)
        device_id = get_device_id(
            event.device, data_bits=event_config.get(CONF_DATA_BITS)
        )
        device_bits[device_id] = event_config.get(CONF_DATA_BITS)
        if event_config[CONF_FIRE_EVENT]:
            device_events.add(device_id)

    # Declare the Handle event
    def handle_receive(event):
        """Handle received messages from RFXtrx gateway."""
        # Log RFXCOM event
        if not event.device.id_string:
            return

        event_data = {
            "packet_type": event.device.packettype,
            "sub_type": event.device.subtype,
            "type_string": event.device.type_string,
            "id_string": event.device.id_string,
            "data": "".join(f"{x:02x}" for x in event.data),
            "values": getattr(event, "values", None),
        }

        _LOGGER.debug("Receive RFXCOM event: %s", event_data)

        data_bits = get_device_data_bits(event.device, device_bits)
        device_id = get_device_id(event.device, data_bits=data_bits)

        # Callback to HA registered components.
        hass.helpers.dispatcher.dispatcher_send(SIGNAL_EVENT, event, device_id)

        # Signal event to any other listeners
        if device_id in device_events:
            hass.bus.fire(EVENT_RFXTRX_EVENT, event_data)

    device = config[CONF_DEVICE]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    debug = config[CONF_DEBUG]

    if port is not None:
        # If port is set then we create a TCP connection
        rfx_object = rfxtrxmod.Connect(
            (host, port),
            None,
            debug=debug,
            transport_protocol=rfxtrxmod.PyNetworkTransport,
        )
    else:
        rfx_object = rfxtrxmod.Connect(device, None, debug=debug)

    def _start_rfxtrx(event):
        rfx_object.event_callback = handle_receive

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_rfxtrx)

    def _shutdown_rfxtrx(event):
        """Close connection with RFXtrx."""
        rfx_object.close_connection()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_rfxtrx)

    hass.data[DATA_RFXOBJECT] = rfx_object

    def send(call):
        event = call.data[ATTR_EVENT]
        rfx_object.transport.send(event)

    hass.services.register(DOMAIN, SERVICE_SEND, send, schema=SERVICE_SEND_SCHEMA)


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


def get_device_data_bits(device, device_bits):
    """Deduce data bits for device based on a cache of device bits."""
    data_bits = None
    if device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
        for device_id, bits in device_bits.items():
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
                    "rfxtrx: found possible device %s for %s "
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
            id_string = str(masked_id)

    return (f"{device.packettype:x}", f"{device.subtype:x}", id_string)


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

    async def async_added_to_hass(self):
        """Restore RFXtrx device state (ON/OFF)."""
        if self._event:
            self._apply_event(self._event)

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, self._handle_event
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
    def device_state_attributes(self):
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

    def _send_command(self, command, brightness=0):
        rfx_object = self.hass.data[DATA_RFXOBJECT]

        if command == "turn_on":
            for _ in range(self.signal_repetitions):
                self._device.send_on(rfx_object.transport)
            self._state = True

        elif command == "dim":
            for _ in range(self.signal_repetitions):
                self._device.send_dim(rfx_object.transport, brightness)
            self._state = True

        elif command == "turn_off":
            for _ in range(self.signal_repetitions):
                self._device.send_off(rfx_object.transport)
            self._state = False

        elif command == "roll_up":
            for _ in range(self.signal_repetitions):
                self._device.send_open(rfx_object.transport)
            self._state = True

        elif command == "roll_down":
            for _ in range(self.signal_repetitions):
                self._device.send_close(rfx_object.transport)
            self._state = False

        elif command == "stop_roll":
            for _ in range(self.signal_repetitions):
                self._device.send_stop(rfx_object.transport)
            self._state = True

        if self.hass:
            self.schedule_update_ha_state()
