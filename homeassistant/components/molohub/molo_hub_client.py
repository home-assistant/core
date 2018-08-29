"""Client protocol class for Molohub."""
import asyncore
import queue
import socket

from homeassistant.const import __short_version__

from .const import (BUFFER_SIZE, CLIENT_STATUS_BINDED, CLIENT_STATUS_UNBINDED,
                    CLIENT_VERSION, CONFIG_FILE_NAME, STAGE_AUTH_BINDED,
                    STAGE_SERVER_CONNECTED, STAGE_SERVER_UNCONNECTED)
from .molo_client_app import MOLO_CLIENT_APP
from .molo_client_config import MOLO_CONFIGS
from .molo_socket_helper import MoloSocketHelper
from .molo_tcp_pack import MoloTcpPack
from .notify_state import NOTIFY_STATE
from .remote_sesstion import RemoteSession
from .utils import LOGGER, dns_open, get_rand_char, save_local_seed


class MoloHubClient(asyncore.dispatcher):
    """Client protocol class for Molohub."""

    tunnel = {}
    tunnel['protocol'] = 'http'
    tunnel['hostname'] = ''
    tunnel['subdomain'] = ''
    tunnel['rport'] = 0
    tunnel['lhost'] = MOLO_CONFIGS.get_config_object()['ha']['host']
    tunnel['lport'] = MOLO_CONFIGS.get_config_object()['ha']['port']

    client_id = ''
    client_token = ''

    protocol_func_bind_map = {}

    def __init__(self, host, port):
        """Initialize protocol arguments."""
        asyncore.dispatcher.__init__(self)
        self.host = host
        self.port = port
        self.molo_tcp_pack = MoloTcpPack()
        self.ping_dequeue = queue.Queue()
        self.append_recv_buffer = None
        self.append_send_buffer = None
        self.append_connect = None
        self.client_status = None
        self.clear()
        self.init_func_bind_map()

    def handle_connect(self):
        """When connected, this method will be call."""
        LOGGER.debug("server connected")
        self.append_connect = False
        self.send_dict_pack(
            MoloSocketHelper.molo_auth(CLIENT_VERSION,
                                       MOLO_CLIENT_APP.hass_context,
                                       __short_version__))

    def handle_close(self):
        """When closed, this method will be call. clean itself."""
        LOGGER.debug("server closed")
        self.clear()
        data = {}
        self.update_notify_state(data, STAGE_SERVER_UNCONNECTED)
        self.close()

        # close all and restart
        asyncore.close_all()

    def handle_read(self):
        """Handle read message."""
        buff = self.recv(BUFFER_SIZE)
        self.append_recv_buffer += buff
        self.process_molo_tcp_pack()

    def writable(self):
        """If the socket send buffer writable."""
        ping_buffer = MOLO_CLIENT_APP.get_ping_buffer()
        if ping_buffer:
            self.append_send_buffer += ping_buffer

        return self.append_connect or (self.append_send_buffer)

    def handle_write(self):
        """Write socket send buffer."""
        sent = self.send(self.append_send_buffer)
        self.append_send_buffer = self.append_send_buffer[sent:]

    # The above are base class methods.
    def clear(self):
        """Reset client protocol arguments."""
        self.molo_tcp_pack.clear()
        self.append_recv_buffer = bytes()
        self.append_send_buffer = bytes()
        self.append_connect = True
        self.client_status = None

    def sock_connect(self):
        """Connect to host:port."""
        self.clear()
        dns_ip = dns_open(self.host)
        if not dns_ip:
            return
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((dns_ip, self.port))

    def on_start_proxy(self, jdata):
        """Handle on_start_proxy json packet."""
        LOGGER.debug("on_start_proxy %s, %s", self.client_id, str(jdata))

    def on_bind_status(self, jdata):
        """Handle on_bind_status json packet."""
        LOGGER.debug("on_bind_status %s", str(jdata))
        jpayload = jdata['Payload']
        self.client_status = jpayload['Status']
        jpayload['token'] = self.client_token
        if self.client_status == CLIENT_STATUS_BINDED:
            self.update_notify_state(jpayload, STAGE_AUTH_BINDED)
        elif self.client_status == CLIENT_STATUS_UNBINDED:
            self.update_notify_state(jpayload, STAGE_SERVER_CONNECTED)

    def on_req_proxy(self, jdata):
        """Handle on_req_proxy json packet."""
        LOGGER.debug("on_req_proxy, %s, %s, %s, %s", self.host, self.port,
                     self.tunnel['lhost'], self.tunnel['lport'])
        remotesession = RemoteSession(self.client_id, self.host, self.port,
                                      self.tunnel['lhost'],
                                      self.tunnel['lport'])
        remotesession.sock_connect()

    def on_auth_resp(self, jdata):
        """Handle on_auth_resp json packet."""
        LOGGER.debug('on_auth_resp %s', str(jdata))
        self.client_id = jdata['Payload']['ClientId']

        self.send_dict_pack(
            MoloSocketHelper.req_tunnel(self.tunnel['protocol'],
                                        self.tunnel['hostname'],
                                        self.tunnel['subdomain'],
                                        self.tunnel['rport'], self.client_id))

    def on_new_tunnel(self, jdata):
        """Handle on_new_tunnel json packet."""
        LOGGER.debug("on_new_tunnel %s", str(jdata))
        data = jdata['OnlineConfig']
        if 'ping_interval' in jdata['OnlineConfig']:
            MOLO_CLIENT_APP.ping_interval = jdata['OnlineConfig'][
                'ping_interval']
        self.update_notify_state(data)
        if jdata['Payload']['Error'] != '':
            LOGGER.error('Server failed to allocate tunnel: %s',
                         jdata['Payload']['Error'])
            return

        self.client_token = jdata['Payload']['token']
        self.on_bind_status(jdata)

    def on_unbind_auth(self, jdata):
        """Handle on_unbind_auth json packet."""
        LOGGER.debug('on_unbind_auth %s', str(jdata))
        data = jdata['Payload']
        data['token'] = self.client_token
        self.update_notify_state(data, STAGE_SERVER_CONNECTED)

    def on_token_expired(self, jdata):
        """Handle on_token_expired json packet."""
        LOGGER.debug('on_token_expired %s', str(jdata))
        if 'Payload' not in jdata:
            return
        data = jdata['Payload']
        self.client_token = data['token']
        self.update_notify_state(data)

    def on_pong(self, jdata):
        """Handle on_pong json packet."""
        LOGGER.debug('on_pong %s, self token: %s', str(jdata),
                     self.client_token)

    def on_reset_clientid(self, jdata):
        """Handle on_reset_clientid json packet."""
        local_seed = get_rand_char(32).lower()
        save_local_seed(
            MOLO_CLIENT_APP.hass_context.config.path(CONFIG_FILE_NAME),
            local_seed)
        LOGGER.debug("reset clientid %s to %s", self.client_id, local_seed)
        self.handle_close()

    def process_molo_tcp_pack(self):
        """Handle received TCP packet."""
        ret = True
        while ret:
            ret = self.molo_tcp_pack.recv_buffer(self.append_recv_buffer)
            if ret and self.molo_tcp_pack.error_code == MoloTcpPack.ERR_OK:
                self.process_json_pack(self.molo_tcp_pack.body_jdata)
            self.append_recv_buffer = self.molo_tcp_pack.tmp_buffer
        if self.molo_tcp_pack.error_code == MoloTcpPack.ERR_MALFORMED:
            LOGGER.error("tcp pack malformed!")
            self.handle_close()

    def process_json_pack(self, jdata):
        """Handle received json packet."""
        LOGGER.debug("process_json_pack %s", str(jdata))
        if jdata['Type'] in self.protocol_func_bind_map:
            MOLO_CLIENT_APP.reset_activate_time()
            self.protocol_func_bind_map[jdata['Type']](jdata)

    def process_new_tunnel(self, jdata):
        """Handle new tunnel."""
        jpayload = jdata['Payload']
        self.client_id = jpayload['clientid']
        self.client_token = jpayload['token']
        LOGGER.debug("Get client id:%s token:%s", self.client_id,
                     self.client_token)
        data = {}
        data['clientid'] = self.client_id
        data['token'] = self.client_token
        self.update_notify_state(data, STAGE_SERVER_CONNECTED)

    def send_raw_pack(self, raw_data):
        """Send raw data packet."""
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

    def ping_server_buffer(self):
        """Get ping buffer."""
        if not self.client_status:
            return
        body = MoloTcpPack.generate_tcp_buffer(
            MoloSocketHelper.ping(self.client_token, self.client_status))
        return body

    def update_notify_state(self, data, stage=None):
        """Add stage field and inform NOTIFY_STATE to update UI data."""
        LOGGER.debug("Send update nofity state with %s", self.client_status)
        if stage:
            data['stage'] = stage
        NOTIFY_STATE.update_state(data)

    def init_func_bind_map(self):
        """Initialize protocol function bind map."""
        self.protocol_func_bind_map = {
            "StartProxy": self.on_start_proxy,
            "BindStatus": self.on_bind_status,
            "ReqProxy": self.on_req_proxy,
            "AuthResp": self.on_auth_resp,
            "NewTunnel": self.on_new_tunnel,
            "TokenExpired": self.on_token_expired,
            "Pong": self.on_pong,
            "ResetClientid": self.on_reset_clientid
        }
