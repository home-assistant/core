"""Remote proxy session class for Molohub."""
import asyncore
import socket

from .const import BUFFER_SIZE
from .local_session import LocalSession
from .molo_client_app import MOLO_CLIENT_APP
from .molo_client_config import MOLO_CONFIGS
from .molo_socket_helper import MoloSocketHelper
from .molo_tcp_pack import MoloTcpPack
from .utils import LOGGER, dns_open


class RemoteSession(asyncore.dispatcher):
    """Remote proxy session class."""

    tunnel = {}
    tunnel['protocol'] = 'http'
    tunnel['hostname'] = ''
    tunnel['subdomain'] = ''
    tunnel['rport'] = 0
    tunnel['lhost'] = MOLO_CONFIGS.get_config_object()['ha']['host']
    tunnel['lport'] = MOLO_CONFIGS.get_config_object()['ha']['port']

    def __init__(self, client_id, rhost, rport, lhost, lport):
        """Initialize remote session arguments."""
        asyncore.dispatcher.__init__(self)
        self.client_id = client_id
        self.lhost = lhost
        self.lport = lport
        self.rhost = rhost
        self.rport = rport
        self.molo_tcp_pack = MoloTcpPack()
        self.tranparency = None
        self.append_recv_buffer = None
        self.append_send_buffer = None
        self.append_connect = None
        self.client_token = None
        self.clear()

    def handle_connect(self):
        """When connected, this method will be call."""
        LOGGER.debug("server connected(%d)", id(self))
        self.append_connect = False
        self.send_dict_pack(MoloSocketHelper.reg_proxy(self.client_id))

    def handle_close(self):
        """When closed, this method will be call. clean itself."""
        LOGGER.debug("server closed(%d)", id(self))
        self.clear()
        MOLO_CLIENT_APP.local_session_dict.pop(id(self), None)
        local_session = MOLO_CLIENT_APP.local_session_dict.get(id(self))
        if local_session:
            local_session.handle_close()
        self.close()

    def handle_read(self):
        """Handle read message."""
        buff = self.recv(BUFFER_SIZE)
        self.append_recv_buffer += buff
        if self.tranparency:
            self.process_tranparency_pack()
            return
        self.process_molo_tcp_pack()

    def writable(self):
        """If the socket send buffer writable."""
        return self.append_connect or (self.append_send_buffer)

    def handle_write(self):
        """Write socket send buffer."""
        sent = self.send(self.append_send_buffer)
        self.append_send_buffer = self.append_send_buffer[sent:]

    # The above are base class methods.
    def clear(self):
        """Reset remote proxy session arguments."""
        self.molo_tcp_pack.clear()
        self.tranparency = False
        self.append_recv_buffer = bytes()
        self.append_send_buffer = bytes()
        self.append_connect = True

    def sock_connect(self):
        """Connect to host:port."""
        self.clear()
        dns_ip = dns_open(self.rhost)
        if not dns_ip:
            return
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((dns_ip, self.rport))

    def on_start_proxy(self, jdata):
        """Handle Start Proxy."""
        LOGGER.debug("on_start_proxy %s", str(jdata))
        localsession = LocalSession(self.lhost, self.lport)
        MOLO_CLIENT_APP.local_session_dict[id(self)] = localsession
        MOLO_CLIENT_APP.remote_session_dict[id(localsession)] = self
        LOGGER.debug("remote local (%d)<->(%d)", id(self), id(localsession))
        localsession.sock_connect()
        self.tranparency = True
        self.process_tranparency_pack()

    def process_tranparency_pack(self):
        """Handle transparency packet."""
        localsession = MOLO_CLIENT_APP.local_session_dict.get(id(self))
        if not localsession:
            LOGGER.debug(
                "process_tranparency_pack() localsession session not found")
            self.handle_close()
            return
        if self.append_recv_buffer:
            localsession.send_raw_pack(self.append_recv_buffer)
            self.append_recv_buffer = bytes()

    def process_molo_tcp_pack(self):
        """Handle TCP packet."""
        ret = self.molo_tcp_pack.recv_buffer(self.append_recv_buffer)
        if ret and self.molo_tcp_pack.error_code == MoloTcpPack.ERR_OK:
            self.append_recv_buffer = self.molo_tcp_pack.tmp_buffer
            LOGGER.debug("RemoteSession process_molo_tcp_pack body:%s", str(
                self.molo_tcp_pack.body_jdata))
            self.process_json_pack(self.molo_tcp_pack.body_jdata)

        if not self.tranparency:
            if self.molo_tcp_pack.error_code == MoloTcpPack.ERR_MALFORMED:
                LOGGER.error("tcp pack malformed!")
                self.handle_close()

    def process_json_pack(self, jdata):
        """Handle json packet."""
        if jdata['Type'] in self.protocol_func_bind_map:
            self.protocol_func_bind_map[jdata['Type']](self, jdata)

    def send_raw_pack(self, raw_data):
        """Write raw data pack to write buffer."""
        if self.append_connect:
            return
        self.append_send_buffer += raw_data
        self.handle_write()

    def send_dict_pack(self, dict_data):
        """Convert and send dict packet."""
        if self.append_connect:
            return
        body = MoloTcpPack.generate_tcp_buffer(dict_data)
        self.send_raw_pack(body)

    protocol_func_bind_map = {'StartProxy': on_start_proxy}
