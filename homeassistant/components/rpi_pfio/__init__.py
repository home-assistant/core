"""Support for controlling the PiFace Digital I/O module on a RPi."""
import pifacedigitalio as PFIO

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP

DOMAIN = "rpi_pfio"

DATA_PFIO_LISTENER = "pfio_listener"


def setup(hass, config):
    """Set up the Raspberry PI PFIO component."""
    pifacedigital = PFIO.PiFaceDigital()
    hass.data[DATA_PFIO_LISTENER] = PFIO.InputEventListener(chip=pifacedigital)

    def cleanup_pfio(event):
        """Stuff to do before stopping."""
        PFIO.deinit()

    def prepare_pfio(event):
        """Stuff to do when Home Assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_pfio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_pfio)
    PFIO.init()

    return True


def write_output(port, value):
    """Write a value to a PFIO."""
    PFIO.digital_write(port, value)


def read_input(port):
    """Read a value from a PFIO."""
    return PFIO.digital_read(port)


def edge_detect(hass, port, event_callback, settle):
    """Add detection for RISING and FALLING events."""
    hass.data[DATA_PFIO_LISTENER].register(
        port, PFIO.IODIR_BOTH, event_callback, settle_time=settle
    )


def activate_listener(hass):
    """Activate the registered listener events."""
    hass.data[DATA_PFIO_LISTENER].activate()
