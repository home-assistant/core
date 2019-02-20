"""Support for controlling GPIO pins of a Raspberry Pi."""
import logging

REQUIREMENTS = ['gpiozero==1.4.1', 'pigpio==1.42', 'RPi.GPIO==0.6.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'remote_rpi_gpio'


def setup(hass, config):
    """Set up the Raspberry PI GPIO component."""
    def cleanup_gpio(event):
        """Stuff to do before stopping."""
    def prepare_gpio(event):
        """Stuff to do when home assistant starts."""
    return True


def setup_output(address, port, invert_logic):
    """Set up a GPIO as output."""
    from gpiozero import LED  # pylint: disable=import-error
    from gpiozero.pins.pigpio import PiGPIOFactory  # noqa: E501 pylint: disable=import-error

    try:
        return LED(port, active_high=invert_logic,
                   pin_factory=PiGPIOFactory(address))
    except (ValueError, IndexError, KeyError):
        return None


def setup_input(address, port, pull_mode):
    """Set up a GPIO as input."""
    from gpiozero import Button
    from gpiozero.pins.pigpio import PiGPIOFactory

    try:
        return Button(port, pull_up=pull_mode,
                      pin_factory=PiGPIOFactory(address))
    except (ValueError, IndexError, KeyError):
        return None


def write_output(switch, value):
    """Write a value to a GPIO."""
    if value == 1:
        switch.on()
    if value == 0:
        switch.off()


def read_input(button):
    """Read a value from a GPIO."""
    return button.value
