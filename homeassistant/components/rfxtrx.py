"""
homeassistant.components.rfxtrx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to a RFXtrx device.
"""

"""
homeassistant.components.rfxtrx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to a RFXtrx device.

Configuration:

To use Rfxtrx device you will need to add the following to your
configuration.yaml file.

rfxtrx:
  device: /dev/serial/by-id/usb-RFXCOM_RFXtrx433_A1YVC1P0-if00-port0

*Optional*

  debug: True

"""
import logging
from homeassistant.util import slugify

DEPENDENCIES = []
REQUIREMENTS = ['https://github.com/Danielhiversen/pyRFXtrx/archive/' +
                'ec7a1aaddf8270db6e5da1c13d58c1547effd7cf.zip#RFXtrx==0.15']

DOMAIN = "rfxtrx"
CONF_DEVICE = 'device'
CONF_DEBUG = 'debug'
RECEIVED_EVT_SUBSCRIBERS = []
RFX_DEVICES = {}
_LOGGER = logging.getLogger(__name__)
RFXOBJECT = None

def setup(hass, config):
    """ Setup the Rfxtrx component. """

    # Declare the Handle event
    def handle_receive(event):
        """ Callback all subscribers for RFXtrx gateway. """

        # Log RFXCOM event
        entity_id = slugify(event.device.id_string.lower())
        packet_id = "".join("{0:02x}".format(x) for x in event.data)
        entity_name = "%(entity_id)s : %(packet_id)s" % locals()
        _LOGGER.info("Receive RFXCOM event from %s => %s" % (event.device, entity_name))

        # Callback to HA registered components
        for subscriber in RECEIVED_EVT_SUBSCRIBERS:
            subscriber(event)

    # Try to load the RFXtrx module
    try:
        import RFXtrx as rfxtrxmod
    except ImportError:
        _LOGGER.exception("Failed to import rfxtrx")
        return False

    # Init the rfxtrx module
    global RFXOBJECT

    device = config[DOMAIN][CONF_DEVICE]
    try:
        debug = config[DOMAIN][CONF_DEBUG]
    except KeyError:
        debug = False

    RFXOBJECT = rfxtrxmod.Core(device, handle_receive, debug=debug)

    return True

def getRFXObject(packetid):
    """ return the RFXObject with the packetid"""
    try:
        import RFXtrx as rfxtrxmod
    except ImportError:
        _LOGGER.exception("Failed to import rfxtrx")
        return False

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
