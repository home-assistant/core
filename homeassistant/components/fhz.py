"""FHZ 1300 pc component from ELV.

FHZ 1300 pc component from ELV, (FHZ1000 probably works as well).
The device is connected to a pc via USB and can be used
to control FS20 devices wirelessly.

For more details about this component, please refer to the documentation.
https://home-assistant.io/components/fhz/
"""
import logging
import threading
import time
import voluptuous as vol
from typing import Any
from homeassistant.const import (CONF_DEVICE, CONF_TIMEOUT,
                                 CONF_CODE, EVENT_HOMEASSISTANT_STOP)
from homeassistant.exceptions import PlatformNotReady
from serial import SerialException

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'fhz'

DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_CODE = '12341234'
DEFAULT_TIMEOUT = 20    # seconds

HELLO_MESSAGE = bytearray([0x02, 0x01, 0x1f, 0x60])
HELLO_MESSAGE_ALTERNATE = bytearray([0x02, 0x01, 0x1f, 0x0a])
ANSWER_TO_HELLO_MESSAGE = bytearray(
    [0x81, 0x0C, 0xC9, 0xA1, 0x01, 0x02, 0x1F,
     0x04, 0xA0, 0x07, 0x5C, 0x35, 0x40, 0x03])
FS20INIT = bytearray([0xc9, 0x01, 0x96])
FS20INIT_ALTERNATE = bytearray([0xc9, 0x01, 0x96, 0x02])
HMS_INIT = bytearray([0xc9, 0x01, 0x86])
HMS_STOP = bytearray([0xc9, 0x01, 0x97])
GET_FREE_MEMORY = bytearray([0xc9, 0x01, 0x85])
REQUEST_SERIAL = bytearray([0xc9, 0x01, 0x84, 0x57, 0x02, 0x80])
TELEGRAM_TYPE1 = 0x04
TELEGRAM_TYPE2 = 0xC9
HEADER_LENGTH = 4
START_BYTE = 0x81
COMMAND_OFF = 0x00
COMMAND_DIM1 = 0x01
COMMAND_ON = 0x11
COMMAND_TOGGLE = 0x12
COMMAND_DIM_UP = 0x13
COMMAND_DIM_DOWN = 0x14
COMMAND_DIM_LOOP = 0x15
COMMAND_TIMER_PROG = 0x16
COMMAND_DELIVERY_STATE = 0x1b

DEVICE = None


def setup(hass, config):
    """Set up the connection to the fhz1300pc device."""
    global DEVICE

    from serial import (Serial,
                        EIGHTBITS, PARITY_NONE, STOPBITS_ONE)

    usb_device = config[DOMAIN].get(CONF_DEVICE, DEFAULT_DEVICE)
    timeout = config[DOMAIN].get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    housecode = config[DOMAIN].get(CONF_CODE, DEFAULT_CODE)

    try:
        serial = Serial()
        serial.baudrate = 9600
        serial.port = usb_device
        serial.bytesize = EIGHTBITS
        serial.parity = PARITY_NONE
        serial.stopbits = STOPBITS_ONE
        serial.timeout = 0.5
        serial.open()

    except SerialException as exc:
        _LOGGER.exception(
            "Unable to open serial port for FHZ 1300 pc: %s", exc)
        return False

    try:
        housecode = base4plus1_length_8(housecode)
    except vol.Invalid as exc:
        _LOGGER.exception("Unable to parse housecode: %s", exc)
        return False

    try:
        DEVICE = FhzDevice(serial, timeout, code_to_int(housecode))
    except PlatformNotReady as exc:
        _LOGGER.exception(
            "Device on '%s' does not seem to be a FHZ 1300 device: %s",
            usb_device, exc)
        serial.close()
        return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, home_assistant_stopped)
    return True


def home_assistant_stopped(*args):
    """Clean up things because HAS stopped."""
    global DEVICE

    if DEVICE is not None:
        DEVICE.stop()
        DEVICE = None


class FhzDevice():
    """Class representing the FHZ1000/FHZ1300 usb device."""

    def __init__(self, serial, timeout, housecode):
        """Init the device."""
        self._serial = serial
        self._buffer_in = bytearray()
        self._buffer_out = bytearray()
        self._serial.rts = True
        self._serial.dtr = True
        self._housecode = housecode
        self._reader = ReadThreadToVoid(serial)
        self._say_hello_to_device(timeout)
        self._reader.start()
        self._write(HMS_INIT, TELEGRAM_TYPE1)
        self._write(GET_FREE_MEMORY, TELEGRAM_TYPE1)
        self._write(FS20INIT_ALTERNATE, TELEGRAM_TYPE1)

    def _say_hello_to_device(self, timeout):
        checkingreader = ReadThreadForCheckingReplyToHello(
            self._serial, self._buffer_in)
        checkingreader.start()
        self._write(HELLO_MESSAGE_ALTERNATE, TELEGRAM_TYPE2)
        start_time = time.time()
        is_timed_out = False
        while checkingreader.isAlive() and (not is_timed_out):
            time.sleep(0.1)
            is_timed_out = (time.time() - start_time) > timeout
        if is_timed_out:
            checkingreader.must_continue = False
            raise PlatformNotReady(
                "No response to HELLO MESSAGE (timed out)",
                self._serial.port)
        if len(self._buffer_in) < 2:
            raise PlatformNotReady(
                "No valid response to HELLO MESSAGE",
                self._serial.port)
        self._buffer_in = self._buffer_in[len(self._buffer_in):]

    def __del__(self):
        """Destructor."""
        if self._reader:
            self._reader.must_continue = False
            self._reader = None
        if self._serial:
            self._serial.close()
            self._serial = None

    def stop(self):
        """Stop the device."""
        self._write(HMS_STOP, TELEGRAM_TYPE1)
        self._write(HMS_STOP, TELEGRAM_TYPE1)
        self._reader.must_continue = False
        self._reader = None
        self._serial.close()
        self._serial = None

    def send_fs20_command(self, button, command, number_of_repeats):
        """
        Send a command to the device.

        Button: code of the button as bytearray,
        Command: COMMAND_ON, COMMAND_OFF etc.
        """
        command_data = bytearray([2, 1, 1, 0, 0, 0, 0])
        command_data[3] = (self._housecode >> 8) & 0xFF
        command_data[4] = self._housecode & 0xFF
        command_data[5] = button
        command_data[6] = command
        i = 0
        while i < number_of_repeats:
            self._write(command_data, TELEGRAM_TYPE1)
            time.sleep(1.0)
            i += 1

    def _write(self, message, telegram_type):
        data = encode(message, telegram_type)
        self._buffer_out.extend(data)
        self._handle_serial_write()

    def _handle_serial_write(self):
        """Writing to serial port."""
        try:
            num_of_bytes_written = self._serial.write(bytes(self._buffer_out))
            self._buffer_out = self._buffer_out[num_of_bytes_written:]
            return True
        except SerialException:
            return False


class ReadThreadForCheckingReplyToHello(threading.Thread):
    """Perform some sanity checks on the answer received from the device."""

    def __init__(self, serial, buffer_in):
        """Constructor."""
        super(ReadThreadForCheckingReplyToHello, self).__init__()
        self._serial = serial
        self._buffer_in = buffer_in
        self.must_continue = True

    def run(self):
        """Override the run method."""
        count = 0
        expected_size = -1
        while self.must_continue:
            byte_array = self._serial.read(1)
            if byte_array:
                self._buffer_in.extend(byte_array)
                count = count + 1
                if count == 1 and byte_array[0] != START_BYTE:
                    self.must_continue = False
                if count == 2:
                    expected_size = byte_array[0] + 2
                if count == expected_size:
                    self.must_continue = False


class ReadThreadToVoid(threading.Thread):
    """Make sure the incoming buffer does not overflow."""

    def __init__(self, serial):
        """Constructor."""
        super(ReadThreadToVoid, self).__init__()
        self._serial = serial
        self.must_continue = True

    def run(self):
        """Override the run method."""
        while self.must_continue:
            byte_array = self._serial.read(2)
            if byte_array:
                if byte_array[0] == START_BYTE:
                    self._serial.read(byte_array[1])
                else:
                    _LOGGER.error("Unexpected data received from device")


def encode(message, telegram_type):
    """Encode a message to a format ready for the device."""
    result = bytearray(HEADER_LENGTH)
    result.extend(message)
    result[0] = START_BYTE
    result[1] = len(message) + 2
    result[2] = telegram_type
    result[3] = sum(message) & 0xFF
    return result


def code_to_int(value):
    """Convert an address string to the 'base 4 + 1' format."""
    result = 0
    for i in value:
        result = result << 2
        result += (int(i) - 1) & 0x03
    return result


def base4plus1(value: Any, length) -> str:
    """Validator for device codes used for FHZ and FS20 devices."""
    valid_values = ['1', '2', '3', '4']
    test = value.strip()
    if len(test) != length:
        raise vol.Invalid('Code has invalid length ({} instead of {})'. format(
            len(test), length))
    for i in test:
        if i not in valid_values:
            raise vol.Invalid(
                "Code has invalid content (" + test + "). " +
                "It must be a sequence of values from [1,2,3,4].")
    return test


def base4plus1_length_4(value: Any) -> str:
    """Validator for FS20 device code."""
    return base4plus1(value, 4)


def base4plus1_length_8(value: Any) -> str:
    """Validator for FHZ device code."""
    return base4plus1(value, 8)
