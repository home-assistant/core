"""Local proxy session class for Molohub."""
import asyncore
import socket

from .const import BUFFER_SIZE
from .molo_client_app import MOLO_CLIENT_APP
from .utils import LOGGER, dns_open


class LocalSession(asyncore.dispatcher):
    """Local proxy session class."""

    def __init__(self, host, port):
        """Initialize local proxy session arguments."""
        asyncore.dispatcher.__init__(self)
        self.host = host
        self.port = port
        self.append_send_buffer = None
        self.append_connect = None
        self.clear()

    def handle_connect(self):
        """When connected, this method will be call."""
        LOGGER.debug("local session connected(%d)", id(self))
        self.append_connect = False

    def handle_close(self):
        """When closed, this method will be call. clean itself."""
        self.clear()
        LOGGER.debug("local session closed(%d)", id(self))
        MOLO_CLIENT_APP.remote_session_dict.pop(id(self), None)
        remote_session = MOLO_CLIENT_APP.remote_session_dict.get(id(self))
        if remote_session:
            remote_session.handle_close()
        self.close()

    def handle_read(self):
        """Handle read message."""
        buff = self.recv(BUFFER_SIZE)
        if not buff:
            return
        remotesession = MOLO_CLIENT_APP.remote_session_dict.get(id(self))
        if not remotesession:
            LOGGER.error("LocalSession handle_read remove session not found")
            self.handle_close()
            return
        LOGGER.debug("local session handle_read %s", buff)
        remotesession.send_raw_pack(buff)

    def writable(self):
        """If the socket send buffer writable."""
        return self.append_connect or (self.append_send_buffer)

    def handle_write(self):
        """Write socket send buffer."""
        sent = self.send(self.append_send_buffer)
        self.append_send_buffer = self.append_send_buffer[sent:]

    # The above are base class methods.
    def clear(self):
        """Reset local proxy session arguments."""
        self.append_send_buffer = bytes()
        self.append_connect = True

    def sock_connect(self):
        """Connect to host:port."""
        self.clear()
        dns_ip = dns_open(self.host)
        if not dns_ip:
            return
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((dns_ip, self.port))

    def send_raw_pack(self, raw_data):
        """Write raw data pack to write buffer."""
        self.append_send_buffer += raw_data
        LOGGER.debug("local session send_raw_pack %s", raw_data)
        if not self.append_connect:
            self.handle_write()
