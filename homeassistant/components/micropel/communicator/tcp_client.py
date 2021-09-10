"""TCP client."""
import logging
import socket
import threading
from typing import Optional

from ..helper.crypto import Crypto
from ..helper.exceptions import ExceptionResponse, MicropelException
from ..helper.message import Message

_LOGGER = logging.getLogger(__name__)


class TcpClient:
    """TCP client."""

    def __init__(self, host: str, port: int, password: int):
        """TCP client constructor."""

        self._lock = threading.Lock()
        self._host = host
        self._port = port
        self._password = password
        self._cryptography = Crypto()
        self._cryptography.crypt_init(password)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(20)
        self._connected = False

    def connect(self):
        """Connect to server."""
        try:
            _LOGGER.debug("Connecting to %s port %s", self._host, self._port)
            self._socket.connect((self._host, self._port))
            self._connected = True
        except OSError as e:
            self._connected = False
            _LOGGER.error("Cannot connect to %s port %s: %s", self._host, self._port, e)

    def send_and_receive(self, message: str) -> Optional[str]:
        """Send and receive data from server."""
        with self._lock:
            try:
                if not self._connected:
                    self.connect()
                request = self._cryptography.code_string(message)
                request += "\r"
                wait = True
                self._socket.sendall(request.encode("utf-8"))
                while wait:
                    response = self._socket.recv(1024)
                    response_str = response.decode("utf-8")
                    response_str = self._cryptography.decode_string(response_str)
                    cmd_id = Message.get_cmd_id(response_str)
                    if cmd_id != "6E":
                        wait = False
                if Message.is_valid_message(response_str):
                    raise MicropelException
                if Message.get_cmd_type(response_str) == "!":
                    raise ExceptionResponse
                data = Message.get_data(response_str)
                return data
            except OSError as e:
                self._connected = False
                _LOGGER.error(
                    "Cannot send message to %s port %s: %s", self._host, self._port, e
                )
        return None

    def close(self):
        """Close connection with server."""
        _LOGGER.debug("Closing socket")
        self._connected = False
        self._socket.close()
