"""Mockup for the numato component interface."""
from numato_gpio import NumatoGpioError


class NumatoModuleMock:
    """Mockup for the numato_gpio module."""

    NumatoGpioError = NumatoGpioError

    class NumatoDeviceMock:
        """Mockup for the numato_gpio.NumatoUsbGpio class."""

        def __init__(self, device):
            """Initialize numato device mockup."""
            self.device = device
            self.callbacks = {}
            self.ports = set()
            self.values = {}

        def setup(self, port, direction):
            """Mockup for setup."""
            self.ports.add(port)
            self.values[port] = None

        def write(self, port, value):
            """Mockup for write."""
            self.values[port] = value

        def read(self, port):
            """Mockup for read."""
            return 1

        def adc_read(self, port):
            """Mockup for adc_read."""
            return 1023

        def add_event_detect(self, port, callback, direction):
            """Mockup for add_event_detect."""
            self.callbacks[port] = callback

        def notify(self, enable):
            """Mockup for notify."""

        def mockup_inject_notification(self, port, value):
            """Make the mockup execute a notification callback."""
            self.callbacks[port](port, value)

    devices = {}
    OUT = 0
    IN = 1

    RISING = 1
    FALLING = 2
    BOTH = 3

    @classmethod
    def discover(cls, _=None):
        """Mockup for the numato device discovery.

        Ignore the device list argument, mock discovers /dev/ttyACM0.
        """
        NumatoModuleMock.devices[0] = NumatoModuleMock.NumatoDeviceMock("/dev/ttyACM0")

    @classmethod
    def cleanup(cls):
        """Mockup for the numato device cleanup."""
        NumatoModuleMock.devices.clear()
