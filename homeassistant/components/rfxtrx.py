"""
Support for RFXtrx components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rfxtrx/
"""

import asyncio
import logging
from collections import OrderedDict
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    ATTR_ENTITY_ID, TEMP_CELSIUS,
    CONF_DEVICES
)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyRFXtrx==0.21.1']

DOMAIN = 'rfxtrx'

DEFAULT_SIGNAL_REPETITIONS = 1

ATTR_AUTOMATIC_ADD = 'automatic_add'
ATTR_DEVICE = 'device'
ATTR_DEBUG = 'debug'
ATTR_STATE = 'state'
ATTR_NAME = 'name'
ATTR_FIRE_EVENT = 'fire_event'
ATTR_DATA_TYPE = 'data_type'
ATTR_DUMMY = 'dummy'
CONF_DATA_BITS = 'data_bits'
CONF_AUTOMATIC_ADD = 'automatic_add'
CONF_DATA_TYPE = 'data_type'
CONF_SIGNAL_REPETITIONS = 'signal_repetitions'
CONF_FIRE_EVENT = 'fire_event'
CONF_DUMMY = 'dummy'
CONF_DEVICE = 'device'
CONF_DEBUG = 'debug'
CONF_OFF_DELAY = 'off_delay'
EVENT_BUTTON_PRESSED = 'button_pressed'

DATA_TYPES = OrderedDict([
    ('Temperature', TEMP_CELSIUS),
    ('Temperature2', TEMP_CELSIUS),
    ('Humidity', '%'),
    ('Barometer', ''),
    ('Wind direction', ''),
    ('Rain rate', ''),
    ('Energy usage', 'W'),
    ('Total usage', 'W'),
    ('Sound', ''),
    ('Sensor Status', ''),
    ('Counter value', ''),
    ('UV', 'uv')])

RECEIVED_EVT_SUBSCRIBERS = []
RFX_DEVICES = {}
_LOGGER = logging.getLogger(__name__)
DATA_RFXOBJECT = 'rfxobject'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_DUMMY, default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the RFXtrx component."""
    # Declare the Handle event
    def handle_receive(event):
        """Handle revieved messages from RFXtrx gateway."""
        # Log RFXCOM event
        if not event.device.id_string:
            return
        _LOGGER.debug("Receive RFXCOM event from "
                      "(Device_id: %s Class: %s Sub: %s, Pkt_id: %s)",
                      slugify(event.device.id_string.lower()),
                      event.device.__class__.__name__,
                      event.device.subtype,
                      "".join("{0:02x}".format(x) for x in event.data))

        # Callback to HA registered components.
        for subscriber in RECEIVED_EVT_SUBSCRIBERS:
            subscriber(event)

    # Try to load the RFXtrx module.
    import RFXtrx as rfxtrxmod

    device = config[DOMAIN][ATTR_DEVICE]
    debug = config[DOMAIN][ATTR_DEBUG]
    dummy_connection = config[DOMAIN][ATTR_DUMMY]

    if dummy_connection:
        rfx_object = rfxtrxmod.Connect(
            device, None, debug=debug,
            transport_protocol=rfxtrxmod.DummyTransport2)
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
    import RFXtrx as rfxtrxmod

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
    return obj


def get_pt2262_deviceid(device_id, nb_data_bits):
    """Extract and return the address bits from a Lighting4/PT2262 packet."""
    if nb_data_bits is None:
        return
    import binascii
    try:
        data = bytearray.fromhex(device_id)
    except ValueError:
        return None
    mask = 0xFF & ~((1 << nb_data_bits) - 1)

    data[len(data)-1] &= mask

    return binascii.hexlify(data)


def get_pt2262_cmd(device_id, data_bits):
    """Extract and return the data bits from a Lighting4/PT2262 packet."""
    try:
        data = bytearray.fromhex(device_id)
    except ValueError:
        return None

    mask = 0xFF & ((1 << data_bits) - 1)

    return hex(data[-1] & mask)


# pylint: disable=unused-variable
def get_pt2262_device(device_id):
    """Look for the device which id matches the given device_id parameter."""
    for dev_id, device in RFX_DEVICES.items():
        if (hasattr(device, 'is_lighting4') and
                device.masked_id == get_pt2262_deviceid(device_id,
                                                        device.data_bits)):
            _LOGGER.debug("rfxtrx: found matching device %s for %s",
                          device_id,
                          device.masked_id)
            return device
    return None


# pylint: disable=unused-variable
def find_possible_pt2262_device(device_id):
    """Look for the device which id matches the given device_id parameter."""
    for dev_id, device in RFX_DEVICES.items():
        if hasattr(device, 'is_lighting4') and len(dev_id) == len(device_id):
            size = None
            for i in range(0, len(dev_id)):
                if dev_id[i] != device_id[i]:
                    break
                size = i

            if size is not None:
                size = len(dev_id) - size - 1
                _LOGGER.info("rfxtrx: found possible device %s for %s "
                             "with the following configuration:\n"
                             "data_bits=%d\n"
                             "command_on=0x%s\n"
                             "command_off=0x%s\n",
                             device_id,
                             dev_id,
                             size * 4,
                             dev_id[-size:], device_id[-size:])
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

        new_device = device(entity_info[ATTR_NAME], event, datas,
                            signal_repetitions)
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

    pkt_id = "".join("{0:02x}".format(x) for x in event.data)
    _LOGGER.debug(
        "Automatic add %s rfxtrx device (Class: %s Sub: %s Packet_id: %s)",
        device_id,
        event.device.__class__.__name__,
        event.device.subtype,
        pkt_id
    )
    datas = {ATTR_STATE: False, ATTR_FIRE_EVENT: False}
    signal_repetitions = config[CONF_SIGNAL_REPETITIONS]
    new_device = device(pkt_id, event, datas,
                        signal_repetitions)
    RFX_DEVICES[device_id] = new_device
    return new_device


def apply_received_command(event):
    """Apply command from rfxtrx."""
    device_id = slugify(event.device.id_string.lower())
    # Check if entity exists or previously added automatically
    if device_id not in RFX_DEVICES:
        return

    _LOGGER.debug(
        "Device_id: %s device_update. Command: %s",
        device_id,
        event.values['Command']
    )

    if event.values['Command'] == 'On'\
            or event.values['Command'] == 'Off':

        # Update the rfxtrx device state
        is_on = event.values['Command'] == 'On'
        RFX_DEVICES[device_id].update_state(is_on)

    elif hasattr(RFX_DEVICES[device_id], 'brightness')\
            and event.values['Command'] == 'Set level':
        _brightness = (event.values['Dim level'] * 255 // 100)

        # Update the rfxtrx device state
        is_on = _brightness > 0
        RFX_DEVICES[device_id].update_state(is_on, _brightness)

    # Fire event
    if RFX_DEVICES[device_id].should_fire_event:
        RFX_DEVICES[device_id].hass.bus.fire(
            EVENT_BUTTON_PRESSED, {
                ATTR_ENTITY_ID:
                    RFX_DEVICES[device_id].entity_id,
                ATTR_STATE: event.values['Command'].lower()
            }
        )
        _LOGGER.debug(
            "Rfxtrx fired event: (event_type: %s, %s: %s, %s: %s)",
            EVENT_BUTTON_PRESSED,
            ATTR_ENTITY_ID,
            RFX_DEVICES[device_id].entity_id,
            ATTR_STATE,
            event.values['Command'].lower()
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
        self._brightness = 0
        self.added_to_hass = False

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Subscribe RFXtrx events."""
        self.added_to_hass = True

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

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")

    def update_state(self, state, brightness=0):
        """Update det state of the device."""
        self._state = state
        self._brightness = brightness
        if self.added_to_hass:
            self.schedule_update_ha_state()

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

        elif command == 'turn_off':
            for _ in range(self.signal_repetitions):
                self._event.device.send_off(rfx_object.transport)
            self._state = False
            self._brightness = 0

        elif command == "roll_up":
            for _ in range(self.signal_repetitions):
                self._event.device.send_open(rfx_object.transport)

        elif command == "roll_down":
            for _ in range(self.signal_repetitions):
                self._event.device.send_close(rfx_object.transport)

        elif command == "stop_roll":
            for _ in range(self.signal_repetitions):
                self._event.device.send_stop(rfx_object.transport)

        if self.added_to_hass:
            self.schedule_update_ha_state()
