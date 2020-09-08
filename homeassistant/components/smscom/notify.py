"""SMS COM platform for notify component."""
import logging
import time

from homeassistant.components.notify import (ATTR_TARGET, PLATFORM_SCHEMA,
                                             BaseNotificationService)
from homeassistant.const import CONF_RECIPIENT
import homeassistant.helpers.config_validation as cv
from serial import Serial
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

CONF_PORT = "com_port"
DEFAULT_PORT = "/dev/ttyUSB0"
CONF_BAUDRATE = "com_baudrate"
DEFAULT_BAUDRATE = 115200

PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
                vol.Required(CONF_RECIPIENT, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    )
)

serial = Serial()


def get_service(hass, config, discovery_info=None):
    """Get the atSMS notification service."""

    serial.port = config[CONF_PORT]
    serial.baudrate = config[CONF_BAUDRATE]
    serial.timeout = 1

    if not _check_com_port(config):
        _LOGGER.error("Can't access to %s", config[CONF_PORT])
        return None
    return SMSComNotificationService(config)


class StaticWait:
    """Wait sendding by static variable."""

    still_sending = False


class SMSComNotificationService(BaseNotificationService):
    """Implementation of a notification service for the SMS Com service."""

    def __init__(self, config):
        """Initialize the service."""
        self.port = config[CONF_PORT]
        self.recipients = config[CONF_RECIPIENT]

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        phones = kwargs.get(ATTR_TARGET, self.recipients)
        while StaticWait.still_sending:
            time.sleep(1)

        StaticWait.still_sending = True
        for phone in phones:
            _LOGGER.debug("Send message to:\r\n%s", phone)
            if not serial.is_open:
                serial.open()
            serial.write(b"AT+CMGF=1\r\n")
            line = _uart_read_timeout(2)
            if line != b"OK":
                _LOGGER.error(line)
                break
            serial.write(b'AT+CMGS="' + phone.encode("ascii") + b'"\r\n')
            line = _uart_read_timeout(2)
            if line != b">":
                _LOGGER.error(line)
                break
            serial.write(message.encode("ascii"))
            serial.write(chr(26).encode("ascii"))
            line = _uart_read_timeout(60)
            # if line != b'OK':
            #     _LOGGER.error(line)
            #     return
            _LOGGER.debug("AT return is:\r\n%s", line)

        StaticWait.still_sending = False
        if serial.is_open:
            serial.close()


def _uart_read_timeout(wait_time):
    serial.timeout = 1
    timeout = time.time() + float(wait_time)
    line = b""
    serial.flush()
    while line == b"":
        line = serial.read(1000).strip()
        if time.time() > timeout:
            break

    serial.flush()
    return line


def _check_com_port(config):
    if not serial.is_open:
        serial.open()
    serial.write(b"ATE0\r\n")
    line = _uart_read_timeout(2)
    if line != b"OK":
        return False
    serial.write(b"AT\r\n")
    line = _uart_read_timeout(2)
    if line != b"OK":
        return False
    if serial.is_open:
        serial.close()

    if line.strip() != b'OK':
        return False
    return True
