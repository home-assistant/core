"""Support for RFXtrx devices."""
import binascii
from collections import OrderedDict
import logging

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_STATE,
    CONF_DEVICE,
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

DOMAIN = "rfxtrx"

DEFAULT_SIGNAL_REPETITIONS = 1

ATTR_AUTOMATIC_ADD = "automatic_add"
ATTR_DEVICE = "device"
ATTR_DEBUG = "debug"
ATTR_FIRE_EVENT = "fire_event"
ATTR_DATA_TYPE = "data_type"
ATTR_DUMMY = "dummy"
CONF_DATA_BITS = "data_bits"
CONF_AUTOMATIC_ADD = "automatic_add"
CONF_DATA_TYPE = "data_type"
CONF_SIGNAL_REPETITIONS = "signal_repetitions"
CONF_FIRE_EVENT = "fire_event"
CONF_DUMMY = "dummy"
CONF_DEBUG = "debug"
CONF_OFF_DELAY = "off_delay"
EVENT_BUTTON_PRESSED = "button_pressed"
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
        ("Battery numeric", ""),
        ("Rssi numeric", ""),
    ]
)

RFX_DEVICES = {}
_LOGGER = logging.getLogger(__name__)
DATA_RFXOBJECT = "rfxobject"

BASE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_DUMMY, default=False): cv.boolean,
    }
)

DEVICE_SCHEMA = BASE_SCHEMA.extend({vol.Required(CONF_DEVICE): cv.string})

PORT_SCHEMA = BASE_SCHEMA.extend(
    {vol.Required(CONF_PORT): cv.port, vol.Optional(CONF_HOST): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(DEVICE_SCHEMA, PORT_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


def setup(hass, config):
    """Set up the RFXtrx component."""
    # Declare the Handle event
    def handle_receive(event):
        """Handle received messages from RFXtrx gateway."""
        # Log RFXCOM event
        if not event.device.id_string:
            return
        _LOGGER.debug(
            "Receive RFXCOM event from "
            "(Device_id: %s Class: %s Sub: %s, Pkt_id: %s)",
            slugify(event.device.id_string.lower()),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )

        # Callback to HA registered components.
        hass.helpers.dispatcher.dispatcher_send(SIGNAL_EVENT, event)

    device = config[DOMAIN].get(ATTR_DEVICE)
    host = config[DOMAIN].get(CONF_HOST)
    port = config[DOMAIN].get(CONF_PORT)
    debug = config[DOMAIN][ATTR_DEBUG]
    dummy_connection = config[DOMAIN][ATTR_DUMMY]

    if dummy_connection:
        rfx_object = rfxtrxmod.Connect(
            device, None, debug=debug, transport_protocol=rfxtrxmod.DummyTransport2,
        )
    elif port is not None:
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
    return True


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


def get_pt2262_device(device_id):
    """Look for the device which id matches the given device_id parameter."""
    for device in RFX_DEVICES.values():
        if (
            hasattr(device, "is_lighting4")
            and device.masked_id is not None
            and device.masked_id == get_pt2262_deviceid(device_id, device.data_bits)
        ):
            _LOGGER.debug(
                "rfxtrx: found matching device %s for %s", device_id, device.masked_id,
            )
            return device
    return None


def find_possible_pt2262_device(device_id):
    """Look for the device which id matches the given device_id parameter."""
    for dev_id, device in RFX_DEVICES.items():
        if hasattr(device, "is_lighting4") and len(dev_id) == len(device_id):
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
                return device

    return None


def get_devices_from_config(config, device):
    """Read rfxtrx configuration."""
    signal_repetitions = config[CONF_SIGNAL_REPETITIONS]

    devices = []
    for packet_id, entity_info in config[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        device_id = slugify(event.device.id_string.lower())
        if device_id in RFX_DEVICES:
            continue
        _LOGGER.debug("Add %s rfxtrx", entity_info[ATTR_NAME])

        # Check if i must fire event
        fire_event = entity_info[ATTR_FIRE_EVENT]
        datas = {ATTR_STATE: False, ATTR_FIRE_EVENT: fire_event}

        new_device = device(entity_info[ATTR_NAME], event, datas, signal_repetitions)
        RFX_DEVICES[device_id] = new_device
        devices.append(new_device)
    return devices


def get_new_device(event, config, device):
    """Add entity if not exist and the automatic_add is True."""
    device_id = slugify(event.device.id_string.lower())
    if device_id in RFX_DEVICES:
        return

    if not config[ATTR_AUTOMATIC_ADD]:
        return

    pkt_id = "".join(f"{x:02x}" for x in event.data)
    _LOGGER.debug(
        "Automatic add %s rfxtrx device (Class: %s Sub: %s Packet_id: %s)",
        device_id,
        event.device.__class__.__name__,
        event.device.subtype,
        pkt_id,
    )
    datas = {ATTR_STATE: False, ATTR_FIRE_EVENT: False}
    signal_repetitions = config[CONF_SIGNAL_REPETITIONS]
    new_device = device(pkt_id, event, datas, signal_repetitions)
    RFX_DEVICES[device_id] = new_device
    return new_device


def fire_command_event(hass, entity_id, command):
    """Fire a command event."""
    hass.bus.fire(
        EVENT_BUTTON_PRESSED, {ATTR_ENTITY_ID: entity_id, ATTR_STATE: command.lower()}
    )
    _LOGGER.debug(
        "Rfxtrx fired event: (event_type: %s, %s: %s, %s: %s)",
        EVENT_BUTTON_PRESSED,
        ATTR_ENTITY_ID,
        entity_id,
        ATTR_STATE,
        command.lower(),
    )


class RfxtrxDevice(Entity):
    """Represents a Rfxtrx device.

    Contains the common logic for Rfxtrx lights and switches.
    """

    def __init__(self, name, event, datas, signal_repetitions):
        """Initialize the device."""
        self.signal_repetitions = signal_repetitions
        self._name = name
        self._event = event
        self._state = datas[ATTR_STATE]
        self._should_fire_event = datas[ATTR_FIRE_EVENT]
        self._unique_id = f"{slugify(self._event.device.type_string.lower())}_{slugify(self._event.device.id_string.lower())}"

    @property
    def should_poll(self):
        """No polling needed for a RFXtrx switch."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def should_fire_event(self):
        """Return is the device must fire event."""
        return self._should_fire_event

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def unique_id(self):
        """Return unique identifier of remote device."""
        return self._unique_id

    def _apply_event(self, event):
        """Apply a received event."""

    def _send_command(self, command, brightness=0):
        if not self._event:
            return
        rfx_object = self.hass.data[DATA_RFXOBJECT]

        if command == "turn_on":
            for _ in range(self.signal_repetitions):
                self._event.device.send_on(rfx_object.transport)
            self._state = True

        elif command == "dim":
            for _ in range(self.signal_repetitions):
                self._event.device.send_dim(rfx_object.transport, brightness)
            self._state = True

        elif command == "turn_off":
            for _ in range(self.signal_repetitions):
                self._event.device.send_off(rfx_object.transport)
            self._state = False

        elif command == "roll_up":
            for _ in range(self.signal_repetitions):
                self._event.device.send_open(rfx_object.transport)
            self._state = True

        elif command == "roll_down":
            for _ in range(self.signal_repetitions):
                self._event.device.send_close(rfx_object.transport)
            self._state = False

        elif command == "stop_roll":
            for _ in range(self.signal_repetitions):
                self._event.device.send_stop(rfx_object.transport)
            self._state = True

        if self.hass:
            self.schedule_update_ha_state()
