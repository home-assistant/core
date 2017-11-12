"""Test FHZ 1300 pc component."""
import unittest
from unittest.mock import patch
import time

from homeassistant import setup
from homeassistant.components import fhz
from homeassistant.exceptions import PlatformNotReady
import voluptuous as vol

from tests.common import get_test_home_assistant


def test_encoding():
    """Test encoding of messages into byte arrays ready for the device."""
    result = fhz.encode(fhz.HELLO_MESSAGE_ALTERNATE, fhz.TELEGRAM_TYPE2)
    assert len(result) == 8
    assert result[0] == 0x81
    assert result[1] == 6
    assert result[2] == 0xC9
    assert result[3] == 44
    assert result[4] == fhz.HELLO_MESSAGE_ALTERNATE[0]
    assert result[5] == fhz.HELLO_MESSAGE_ALTERNATE[1]
    assert result[6] == fhz.HELLO_MESSAGE_ALTERNATE[2]
    assert result[7] == fhz.HELLO_MESSAGE_ALTERNATE[3]
    assert sum(fhz.HELLO_MESSAGE_ALTERNATE) == 44


def test_code_to_int():
    """Testing of a code into an integer value."""
    assert fhz.code_to_int("11442442") == 3965
    assert fhz.code_to_int("24121231") == 28952


def test_validator_valid_value():
    """Testing of validators with valid values."""
    assert fhz.base4plus1_length_4(" 4121 ") == "4121"
    assert fhz.base4plus1_length_8("23441121 ") == "23441121"


def test_validator_invalid_length():
    """Testing of validators with invalid length."""
    is_invalid = False
    try:
        fhz.base4plus1_length_4("14321")
        is_invalid = False
    except vol.Invalid as exc:
        is_invalid = True
        assert 'invalid length' in str(exc)
    assert is_invalid
    try:
        fhz.base4plus1_length_8("14321")
        is_invalid = False
    except vol.Invalid as exc:
        is_invalid = True
        assert 'invalid length' in str(exc)
    assert is_invalid


def test_validator_invalid_content():
    """Testing of validators with invalid content."""
    is_invalid = False
    try:
        fhz.base4plus1_length_4("1532")
        is_invalid = False
    except vol.Invalid as exc:
        is_invalid = True
        assert 'invalid content' in str(exc)
    assert is_invalid
    try:
        fhz.base4plus1_length_4("1130")
        is_invalid = False
    except vol.Invalid as exc:
        is_invalid = True
        assert 'invalid content' in str(exc)
    assert is_invalid
    try:
        fhz.base4plus1_length_4("ABCD")
        is_invalid = False
    except vol.Invalid as exc:
        is_invalid = True
        assert 'invalid content' in str(exc)
    assert is_invalid


@patch('serial.Serial')
def test_non_responding_device(mock_serial):
    """Testing of a non responding device."""
    serial = mock_serial()
    is_exception_occured = False
    try:
        fhz.FhzDevice(serial, 0.1, fhz.code_to_int('11442442'))
    except PlatformNotReady as exc:
        is_exception_occured = True
        assert 'No valid response to HELLO MESSAGE' in str(exc)
    assert is_exception_occured
    serial.read.assert_called_with(1)


class TestComponentFhz(unittest.TestCase):
    """Test FHZ component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.buffer_read = bytearray()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_illegal_code(self):
        """Testing of device with invalid code."""
        info = {
            'device': '/dev/ttyUSB0',
            'code': '17821212',
        }
        assert not setup.setup_component(self.hass, fhz.DOMAIN, {'fhz': info})

    def mock_read(self, *args, **kwargs):
        """Mocking the read method of the serial class."""
        num = args[0]
        result = self.buffer_read[0:num]
        self.buffer_read = self.buffer_read[num:]
        return result

    @patch('serial.Serial')
    def test_properly_responding_device(self, mock_serial):
        """Testing of a properly responding device."""
        serial = mock_serial()
        serial.read.side_effect = self.mock_read
        self.buffer_read.extend(fhz.ANSWER_TO_HELLO_MESSAGE)

        is_exception_occured = False
        try:
            fhz.FhzDevice(serial, 0.1, fhz.code_to_int('11442442'))
        except PlatformNotReady:
            is_exception_occured = True
        assert not is_exception_occured
        assert len(self.buffer_read) == 0
        assert serial.write.call_count == 4

    @patch('serial.Serial')
    def test_toggle_lamp_once(self, mock_serial):
        """Send the toggle command once to the device."""
        serial = mock_serial()
        serial.read.side_effect = self.mock_read
        self.buffer_read.extend(fhz.ANSWER_TO_HELLO_MESSAGE)

        device = fhz.FhzDevice(serial, 0.01, fhz.code_to_int('11442442'))
        serial.write.reset_mock()

        button_code = 4
        number_of_repeats = 1
        device.send_fs20_command(
            button_code, fhz.COMMAND_TOGGLE, number_of_repeats)
        time.sleep(0.1)
        assert serial.write.call_count == 1

    @patch('serial.Serial')
    def test_toggle_lamp_repeat_4_times(self, mock_serial):
        """Send the toggle command four times to the device."""
        serial = mock_serial()
        serial.read.side_effect = self.mock_read
        self.buffer_read.extend(fhz.ANSWER_TO_HELLO_MESSAGE)

        device = fhz.FhzDevice(serial, 0.01, fhz.code_to_int('11442442'))
        serial.write.reset_mock()

        button_code = 7
        number_of_repeats = 4
        device.send_fs20_command(
            button_code, fhz.COMMAND_TOGGLE, number_of_repeats)
        time.sleep(0.1)
        assert serial.write.call_count == 4

        # pylint: disable=W0212
        assert device._reader.isAlive()
        assert serial.read.call_count > 14
