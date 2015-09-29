"""
homeassistant.components.rfxtrx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to a RFXtrx device.
"""

import logging

DEPENDENCIES = []
REQUIREMENTS = ['https://github.com/Danielhiversen/pyRFXtrx/archive/' +
                'ec7a1aaddf8270db6e5da1c13d58c1547effd7cf.zip#RFXtrx==0.15']

DOMAIN = "rfxtrx"
CONF_DEVICE = 'device'
RECEIVED_EVT_SUBSCRIBERS = []
RFX_DEVICES = {}
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Setup the Rfxtrx component. """

    # Declare the Handle event
    def handle_receive(event):
        """ Callback all subscribers for RFXtrx gateway. """
        for subscriber in RECEIVED_EVT_SUBSCRIBERS:
            subscriber(event)

    # Try to load the RFXtrx module
    try:
        import RFXtrx as rfxtrxmod
    except ImportError:
        _LOGGER.exception("Failed to import rfxtrx")
        return False

    # Init the rfxtrx module
    device = config[DOMAIN][CONF_DEVICE]
    rfxtrxmod.Core(device, handle_receive)

    return True
