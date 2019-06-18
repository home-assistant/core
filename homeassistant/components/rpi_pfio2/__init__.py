"""Support for controlling the PiFace Digital I/O module on a RPi."""
import logging

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['pifacecommon==4.2.2', 'pifacedigitalio==3.0.5']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'rpi_pfio2'

DATA_PFIO_LISTENER = 'pfio_listener'

BOARD_ADDRESSES = [0,1,2,3]

def setup(hass, config):
    """Set up the Raspberry PI PFIO component."""
    import pifacedigitalio as PFIO
    pifacedigital={}
    hass.data[DATA_PFIO_LISTENER]={}
    for address in BOARD_ADDRESSES:
        try:
            pifacedigital[address] = PFIO.PiFaceDigital(address)
            hass.data[DATA_PFIO_LISTENER][address] = PFIO.InputEventListener(chip=pifacedigital[address])
        except:
            pass

    def cleanup_pfio(event):
        """Stuff to do before stopping."""
        PFIO.deinit()

    def prepare_pfio(event):
        """Stuff to do when home assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_pfio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_pfio)
    PFIO.init()

    return True


def write_output(port, value, hardware_addr=0):
    """Write a value to a PFIO."""
    import pifacedigitalio as PFIO
    PFIO.digital_write(port, value, hardware_addr)


def read_input(port, hardware_addr=0):
    """Read a value from a PFIO."""
    import pifacedigitalio as PFIO
    return PFIO.digital_read(port, hardware_addr)


def edge_detect(hass, port, event_callback, settle, hardware_addr=0):
    """Add detection for RISING and FALLING events."""
    import pifacedigitalio as PFIO
    hass.data[DATA_PFIO_LISTENER][hardware_addr].register(
        port, PFIO.IODIR_BOTH, event_callback, settle_time=settle)


def activate_listener(hass):
    """Activate the registered listener events."""
    for address in hass.data[DATA_PFIO_LISTENER]:
        hass.data[DATA_PFIO_LISTENER][address].activate()
