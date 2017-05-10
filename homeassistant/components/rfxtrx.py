"""
Support for RFXtrx components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rfxtrx/
"""
import logging
from collections import OrderedDict
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity
from homeassistant.const import (ATTR_ENTITY_ID, TEMP_CELSIUS)

REQUIREMENTS = ['pyRFXtrx==0.18.0']

DOMAIN = 'rfxtrx'

DEFAULT_SIGNAL_REPETITIONS = 1

ATTR_AUTOMATIC_ADD = 'automatic_add'
ATTR_DEVICE = 'device'
ATTR_DEBUG = 'debug'
ATTR_STATE = 'state'
ATTR_NAME = 'name'
ATTR_FIREEVENT = 'fire_event'
ATTR_DATA_TYPE = 'data_type'
ATTR_DUMMY = 'dummy'
CONF_SIGNAL_REPETITIONS = 'signal_repetitions'
CONF_DEVICES = 'devices'
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
    ('Counter value', '')])

RECEIVED_EVT_SUBSCRIBERS = []
RFX_DEVICES = {}
_LOGGER = logging.getLogger(__name__)
RFXOBJECT = None


def _valid_device(value, device_type):
    """Validate a dictionary of devices definitions."""
    config = OrderedDict()
    for key, device in value.items():

        # Still accept old configuration
        if 'packetid' in device.keys():
            msg = 'You are using an outdated configuration of the rfxtrx ' +\
                  'device, {}.'.format(key) +\
                  ' Your new config should be:\n    {}: \n        name: {}'\
                  .format(device.get('packetid'),
                          device.get(ATTR_NAME, 'deivce_name'))
            _LOGGER.warning(msg)
            key = device.get('packetid')
            device.pop('packetid')

        key = str(key)
        if not len(key) % 2 == 0:
            key = '0' + key

        if get_rfx_object(key) is None:
            raise vol.Invalid('Rfxtrx device {} is invalid: '
                              'Invalid device id for {}'.format(key, value))

        if device_type == 'sensor':
            config[key] = DEVICE_SCHEMA_SENSOR(device)
        elif device_type == 'light_switch':
            config[key] = DEVICE_SCHEMA(device)
        else:
            raise vol.Invalid('Rfxtrx device is invalid')

        if not config[key][ATTR_NAME]:
            config[key][ATTR_NAME] = key
    return config


def valid_sensor(value):
    """Validate sensor configuration."""
    return _valid_device(value, "sensor")


def _valid_light_switch(value):
    return _valid_device(value, "light_switch")


DEVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
    vol.Optional(ATTR_FIREEVENT, default=False): cv.boolean,
})

DEVICE_SCHEMA_SENSOR = vol.Schema({
    vol.Optional(ATTR_NAME, default=None): cv.string,
    vol.Optional(ATTR_FIREEVENT, default=False): cv.boolean,
    vol.Optional(ATTR_DATA_TYPE, default=[]):
        vol.All(cv.ensure_list, [vol.In(DATA_TYPES.keys())]),
})

DEFAULT_SCHEMA = vol.Schema({
    vol.Required("platform"): DOMAIN,
    vol.Optional(CONF_DEVICES, default={}): vol.All(dict, _valid_light_switch),
    vol.Optional(ATTR_AUTOMATIC_ADD, default=False):  cv.boolean,
    vol.Optional(CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS):
        vol.Coerce(int),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(ATTR_DEVICE): cv.string,
        vol.Optional(ATTR_DEBUG, default=False): cv.boolean,
        vol.Optional(ATTR_DUMMY, default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the RFXtrx component."""
    # Declare the Handle event
    def handle_receive(event):
        """Handle revieved messgaes from RFXtrx gateway."""
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

    # Init the rfxtrx module.
    global RFXOBJECT

    device = config[DOMAIN][ATTR_DEVICE]
    debug = config[DOMAIN][ATTR_DEBUG]
    dummy_connection = config[DOMAIN][ATTR_DUMMY]

    if dummy_connection:
        RFXOBJECT =\
            rfxtrxmod.Connect(device, handle_receive, debug=debug,
                              transport_protocol=rfxtrxmod.DummyTransport2)
    else:
        RFXOBJECT = rfxtrxmod.Connect(device, handle_receive, debug=debug)

    def _shutdown_rfxtrx(event):
        """Close connection with RFXtrx."""
        RFXOBJECT.close_connection()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_rfxtrx)

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


def get_devices_from_config(config, device, hass):
    """Read rfxtrx configuration."""
    signal_repetitions = config[CONF_SIGNAL_REPETITIONS]

    devices = []
    for packet_id, entity_info in config[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        device_id = slugify(event.device.id_string.lower())
        if device_id in RFX_DEVICES:
            continue
        _LOGGER.info("Add %s rfxtrx", entity_info[ATTR_NAME])

        # Check if i must fire event
        fire_event = entity_info[ATTR_FIREEVENT]
        datas = {ATTR_STATE: False, ATTR_FIREEVENT: fire_event}

        new_device = device(entity_info[ATTR_NAME], event, datas,
                            signal_repetitions)
        new_device.hass = hass
        RFX_DEVICES[device_id] = new_device
        devices.append(new_device)
    return devices


def get_new_device(event, config, device, hass):
    """Add entity if not exist and the automatic_add is True."""
    device_id = slugify(event.device.id_string.lower())
    if device_id in RFX_DEVICES:
        return

    if not config[ATTR_AUTOMATIC_ADD]:
        return

    pkt_id = "".join("{0:02x}".format(x) for x in event.data)
    _LOGGER.info(
        "Automatic add %s rfxtrx device (Class: %s Sub: %s Packet_id: %s)",
        device_id,
        event.device.__class__.__name__,
        event.device.subtype,
        pkt_id
    )
    datas = {ATTR_STATE: False, ATTR_FIREEVENT: False}
    signal_repetitions = config[CONF_SIGNAL_REPETITIONS]
    new_device = device(pkt_id, event, datas,
                        signal_repetitions)
    new_device.hass = hass
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
        _LOGGER.info(
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
        self._should_fire_event = datas[ATTR_FIREEVENT]
        self._brightness = 0

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
        self.schedule_update_ha_state()

    def _send_command(self, command, brightness=0):
        if not self._event:
            return

        if command == "turn_on":
            for _ in range(self.signal_repetitions):
                self._event.device.send_on(RFXOBJECT.transport)
            self._state = True

        elif command == "dim":
            for _ in range(self.signal_repetitions):
                self._event.device.send_dim(RFXOBJECT.transport,
                                            brightness)
            self._state = True

        elif command == 'turn_off':
            for _ in range(self.signal_repetitions):
                self._event.device.send_off(RFXOBJECT.transport)
            self._state = False
            self._brightness = 0

        elif command == "roll_up":
            for _ in range(self.signal_repetitions):
                self._event.device.send_open(RFXOBJECT.transport)

        elif command == "roll_down":
            for _ in range(self.signal_repetitions):
                self._event.device.send_close(RFXOBJECT.transport)

        elif command == "stop_roll":
            for _ in range(self.signal_repetitions):
                self._event.device.send_stop(RFXOBJECT.transport)

        self.schedule_update_ha_state()
