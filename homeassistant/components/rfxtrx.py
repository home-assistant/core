"""
Support for RFXtrx components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rfxtrx/
"""
import logging

from homeassistant.util import slugify

REQUIREMENTS = ['https://github.com/Danielhiversen/pyRFXtrx/' +
                'archive/0.5.zip#pyRFXtrx==0.5']

DOMAIN = "rfxtrx"

ATTR_DEVICE = 'device'
ATTR_DEBUG = 'debug'
ATTR_STATE = 'state'
ATTR_NAME = 'name'
ATTR_PACKETID = 'packetid'
ATTR_FIREEVENT = 'fire_event'
ATTR_DATA_TYPE = 'data_type'
ATTR_DUMMY = "dummy"

EVENT_BUTTON_PRESSED = 'button_pressed'

RECEIVED_EVT_SUBSCRIBERS = []
RFX_DEVICES = {}
_LOGGER = logging.getLogger(__name__)
RFXOBJECT = None


def setup(hass, config):
    """Setup the RFXtrx component."""
    # Declare the Handle event
    def handle_receive(event):
        """Callback all subscribers for RFXtrx gateway."""
        # Log RFXCOM event
        if not event.device.id_string:
            return
        entity_id = slugify(event.device.id_string.lower())
        packet_id = "".join("{0:02x}".format(x) for x in event.data)
        entity_name = "%s : %s" % (entity_id, packet_id)
        _LOGGER.info("Receive RFXCOM event from %s => %s",
                     event.device, entity_name)

        # Callback to HA registered components.
        for subscriber in RECEIVED_EVT_SUBSCRIBERS:
            subscriber(event)

    # Try to load the RFXtrx module.
    import RFXtrx as rfxtrxmod

    # Init the rfxtrx module.
    global RFXOBJECT

    if ATTR_DEVICE not in config[DOMAIN]:
        _LOGGER.error(
            "can not find device parameter in %s YAML configuration section",
            DOMAIN
        )
        return False

    device = config[DOMAIN][ATTR_DEVICE]
    debug = config[DOMAIN].get(ATTR_DEBUG, False)
    dummy_connection = config[DOMAIN].get(ATTR_DUMMY, False)

    if dummy_connection:
        RFXOBJECT =\
            rfxtrxmod.Core(device, handle_receive, debug=debug,
                           transport_protocol=rfxtrxmod.DummyTransport2)
    else:
        RFXOBJECT = rfxtrxmod.Core(device, handle_receive, debug=debug)

    return True


def get_rfx_object(packetid):
    """Return the RFXObject with the packetid."""
    import RFXtrx as rfxtrxmod

    binarypacket = bytearray.fromhex(packetid)

    pkt = rfxtrxmod.lowlevel.parse(binarypacket)
    if pkt is not None:
        if isinstance(pkt, rfxtrxmod.lowlevel.SensorPacket):
            obj = rfxtrxmod.SensorEvent(pkt)
        elif isinstance(pkt, rfxtrxmod.lowlevel.Status):
            obj = rfxtrxmod.StatusEvent(pkt)
        else:
            obj = rfxtrxmod.ControlEvent(pkt)

        return obj

    return None
