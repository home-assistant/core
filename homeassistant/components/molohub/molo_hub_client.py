"""Client protocol class for Molohub."""
import asyncore
import queue
import socket

from homeassistant.const import __short_version__

from .const import (BUFFER_SIZE, CLIENT_STATUS_BINDED, CLIENT_STATUS_UNBINDED,
                    CLIENT_VERSION, STAGE_AUTH_BINDED, STAGE_SERVER_CONNECTED,
                    STAGE_SERVER_UNCONNECTED)
from .molo_client_app import MOLO_CLIENT_APP
from .molo_client_config import MOLO_CONFIGS
from .molo_socket_helper import MoloSocketHelper
from .molo_tcp_pack import MoloTcpPack
from .remote_sesstion import RemoteSession
from .utils import LOGGER, dns_open, fire_molohub_event


class MoloHubClient(asyncore.dispatcher):
    """Client protocol class for Molohub."""

    tunnel = {}
    tunnel['protocol'] = 'http'
    tunnel['hostname'] = ''
    tunnel['subdomain'] = ''
    tunnel['rport'] = 0
    tunnel['lhost'] = MOLO_CONFIGS.config_object['ha']['host']
    tunnel['lport'] = MOLO_CONFIGS.config_object['ha']['port']

    client_id = ''
    client_token = ''

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

    def handle_connect(self):
        """When connected, this method will be call."""
        LOGGER.debug("server connected")
        self.append_connect = False
        self.send_dict_pack(
            MoloSocketHelper.ngrok_auth(CLIENT_VERSION,
                                        MOLO_CLIENT_APP.hass_context,
                                        __short_version__))

    def handle_close(self):
        """When closed, this method will be call. clean itself."""
        LOGGER.debug("server closed")
        self.clear()
        data = {}
        data['stage'] = STAGE_SERVER_UNCONNECTED
        fire_molohub_event(MOLO_CLIENT_APP.hass_context, data)
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
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        dns_ip = dns_open(self.host)
        if not dns_ip:
            return
        self.connect((dns_ip, self.port))

    def on_start_proxy(self, jdata):
        """Handle on_start_proxy json packet."""
        LOGGER.debug('on_start_proxy %s, %s', self.client_id, str(jdata))

    def on_bind_status(self, jdata):
        """Handle on_bind_status json packet."""
        LOGGER.debug("on_bind_status %s", str(jdata))
        jpayload = jdata['Payload']
        self.client_status = jpayload['Status']
        if self.client_status == CLIENT_STATUS_BINDED:
            jpayload['stage'] = STAGE_AUTH_BINDED
        elif self.client_status == CLIENT_STATUS_UNBINDED:
            jpayload['stage'] = STAGE_SERVER_CONNECTED

        # fire molo event
        jpayload['token'] = self.client_token
        fire_molohub_event(MOLO_CLIENT_APP.hass_context, jpayload)

    def on_req_proxy(self, jdata):
        """Handle on_req_proxy json packet."""
        remotesession = RemoteSession(self.client_id, self.host, self.port,
                                      self.tunnel['lhost'],
                                      self.tunnel['lport'])
        MOLO_CLIENT_APP.remote_session_list.append(remotesession)
        remotesession.sock_connect()

    def on_auth_resp(self, jdata):
        """Handle on_auth_resp json packet."""
        LOGGER.debug('on_auth_resp %s', str(jdata))
        self.client_id = jdata['Payload']['ClientId']

        self.send_dict_pack(
            MoloSocketHelper.req_tunnel(
                self.tunnel['protocol'], self.tunnel['hostname'],
                self.tunnel['subdomain'], self.tunnel['rport'],
                self.client_id))

    def on_new_tunnel(self, jdata):
        """Handle on_new_tunnel json packet."""
        LOGGER.debug("on_new_tunnel %s", str(jdata))
        data = jdata['OnlineConfig']
        if 'ping_interval' in jdata['OnlineConfig']:
            MOLO_CLIENT_APP.ping_interval = jdata['OnlineConfig'][
                'ping_interval']
        data['update_ui'] = 'true'
        fire_molohub_event(MOLO_CLIENT_APP.hass_context, data)
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
        data['stage'] = STAGE_SERVER_CONNECTED
        data['token'] = self.client_token
        fire_molohub_event(MOLO_CLIENT_APP.hass_context, data)

    def on_token_expired(self, jdata):
        """Handle on_token_expired json packet."""
        LOGGER.debug('on_token_expired %s', str(jdata))
        if 'Payload' not in jdata:
            return
        data = jdata['Payload']
        self.client_token = data['token']
        data['update_token'] = 'true'
        fire_molohub_event(MOLO_CLIENT_APP.hass_context, data)

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
            self.protocol_func_bind_map[jdata['Type']](self, jdata)

    def process_new_tunnel(self, jdata):
        """Handle new tunnel."""
        jpayload = jdata['Payload']
        self.client_id = jpayload['clientid']
        self.client_token = jpayload['token']
        LOGGER.debug(
            "Get client id:%s token:%s", self.client_id, self.client_token)
        data = {}
        data['stage'] = STAGE_SERVER_CONNECTED
        data['clientid'] = self.client_id
        data['token'] = self.client_token
        fire_molohub_event(MOLO_CLIENT_APP.hass_context, data)

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

    protocol_func_bind_map = {
        "StartProxy": on_start_proxy,
        "BindStatus": on_bind_status,
        "ReqProxy": on_req_proxy,
        "AuthResp": on_auth_resp,
        "NewTunnel": on_new_tunnel,
        "TokenExpired": on_token_expired
    }
