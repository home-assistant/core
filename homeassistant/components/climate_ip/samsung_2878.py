from .connection import (register_connection, Connection)
from .yaml_const import (CONFIG_DEVICE_CONNECTION_PARAMS, CONFIG_DEVICE_POWER_TEMPLATE,
    CONFIG_DEVICE_CONNECTION_TEMPLATE, CONF_CERT, CONFIG_DEVICE_CONNECTION,
)
from homeassistant.const import (CONF_PORT, CONF_TOKEN, CONF_MAC, CONF_IP_ADDRESS)
from .properties import (register_status_getter, DeviceProperty)
from socket import * 
import json
import logging
import sys
import ssl
import traceback
import re
import os

CONNECTION_TYPE_S2878 = 'samsung_2878'

CONF_DUID = 'duid'
CONST_STATUS_OK_STR = 'Status="Okay"'

xml_test = '<?xml version="1.0" encoding="utf-8" ?><Response Type="DeviceState" Status="Okay"><DeviceState><Device DUID="XXXXXXX" GroupID="AC" ModelID="AC" ><Attr ID="AC_FUN_ENABLE" Type="RW" Value="Enable"/><Attr ID="AC_FUN_TEMPNOW" Type="R" Value="79"/><Attr ID="AC_FUN_TEMPSET" Type="RW" Value="24"/><Attr ID="AC_FUN_POWER" Type="RW" Value="On"/><Attr ID="AC_FUN_OPMODE" Type="RW" Value="Cool"/><Attr ID="AC_FUN_WINDLEVEL" Type="RW" Value="Auto"/><Attr ID="AC_FUN_ERROR" Type="R" Value="30303030"/><Attr ID="AC_ADD_STARTWPS" Type="RW" Value="0"/><Attr ID="AC_ADD_APMODE_END" Type="W" Value="0"/></Device></DeviceState></Response>'

class connection_config():
    def __init__(self, host, port, token, cert, duid):
        self.host = host
        self.port = port
        self.token = token
        self.duid = duid
        self.cert = cert
        self.socket = None

@register_connection
class ConnectionSamsung2878(Connection):
    def __init__(self, hass_config, logger):
        super(ConnectionSamsung2878, self).__init__(hass_config, logger)
        self._params = {}
        self._connection_init_template = None
        self._cfg = connection_config(None, None, None, None, None)
        self._device_status = {}
        self._socket_timeout = 1 # in seconds
        self.update_configuration_from_hass(hass_config)
        self._power_template = None

    def update_configuration_from_hass(self, hass_config):
        if hass_config is not None:
            cert_file = hass_config.get(CONF_CERT, None)
            if cert_file == '':
                cert_file = None
            if cert_file is not None:
                if cert_file.find('\\') == -1 and cert_file.find('/') == -1:
                    cert_file = os.path.join(os.path.dirname(__file__), cert_file)

            duid = None
            mac = hass_config.get(CONF_MAC, None)
            if mac is not None:
                duid = re.sub(':', '', mac)
            
            cfg = connection_config(
                hass_config.get(CONF_IP_ADDRESS, None), 
                hass_config.get(CONF_PORT, 2878), 
                hass_config.get(CONF_TOKEN, None),
                cert_file,
                duid)

            self._cfg = cfg
            self._params[CONF_DUID] = cfg.duid
            self._params[CONF_TOKEN] = cfg.token

    def load_from_yaml(self, node, connection_base):
        from jinja2 import Template
        if connection_base is not None:
            self._params.update(connection_base._params.copy())
        
        if node is not None:
            params_node = node.get(CONFIG_DEVICE_CONNECTION_PARAMS, {})
            
            if CONFIG_DEVICE_CONNECTION_TEMPLATE in params_node:
                self._connection_init_template = Template(params_node[CONFIG_DEVICE_CONNECTION_TEMPLATE])
            elif connection_base is None:
                self.logger.error("ERROR: missing 'connection_template' parameter in connection section")
                return False

            if CONFIG_DEVICE_POWER_TEMPLATE in params_node:
                self._power_template = Template(params_node[CONFIG_DEVICE_POWER_TEMPLATE])

            if connection_base is None:
                if self._cfg.host is None:
                    self.logger.error("ERROR: missing 'host' parameter in configuration section")
                    return False
                if self._cfg.token is None or self._cfg.token == '':
                    self.logger.error("ERROR: missing 'token' parameter in configuration section")
                    return False
                if self._cfg.duid == None:
                    self.logger.error("ERROR: missing 'mac' parameter in configuration section")
                    return False
                if self._cfg.cert is None:
                    self.logger.warning("WARNING: 'cert' parameter is empty, skipping certificate validation")
                self.logger.info("Configuration, host: {}:{}".format(self._cfg.host, self._cfg.port))
                self.logger.info("Configuration, token: {}".format(self._cfg.token))
                self.logger.info("Configuration, duid: {}".format(self._cfg.duid))
                self.logger.info("Configuration, cert: {}".format(self._cfg.cert))
            
            self._params.update(params_node)    
            return True

        return False

    @staticmethod
    def match_type(type):
        return type == CONNECTION_TYPE_S2878

    def create_updated(self, node):
        from jinja2 import Template
        c = ConnectionSamsung2878(None, self.logger)
        c._cfg = self._cfg
        c._connection_init_template = self._connection_init_template
        c._power_template = self._power_template
        c.load_from_yaml(node, self)
        return c

    def read_line_from_socket(self, sslSocket):
        import select
        reply = None
        ready = select.select([sslSocket], [], [], self._socket_timeout)
        self.logger.info("Reading data from socket...")
        if ready and ready[0]:
            reply = sslSocket.recv(4096).decode("utf-8")
            self.logger.info("Response: {}".format(reply))
        else:
            self.logger.info("Timed out, no data to read")
        return reply

    def handle_response_invalidate_account(self, sslSocket, response):
        if sslSocket is not None:
            if self._connection_init_template is not None:
                params = self._params
                init_message = self._connection_init_template.render(**params) + '\n'
                self.logger.info("Sending auth command: {}".format(init_message))
                sslSocket.sendall(init_message.encode('utf-8'))
                self.logger.info("Auth command sent")
                self._cfg.socket = sslSocket

    def handle_response_auth_success(self, sslSocket, response):
        self.logger.info('Connection authenticated')
        self._cfg.socket = sslSocket
        command = '<Request Type="DeviceState" DUID="{}"></Request>'.format(self._cfg.duid)
        self.logger.info("Requesting status with command: {}".format(command))
        sslSocket.sendall(command.encode('utf-8'))
        self.logger.info("Status request sent")

    def handle_response_status_update(self, sslSocket, response):
        attrs = response.split("><")
        for attr in attrs:
            f = re.match('Attr ID="(.*)" Value="(.*)"', attr)
            if f:
                k, v = f.group(1, 2)
                self._device_status[k] = v

    def handle_response_device_state(self, sslSocket, response):
        attrs = response.split("><")
        device_status = {}
        for attr in attrs:
            f = re.match('Attr ID="(.*)" Type=".*" Value="(.*)"', attr)
            if f:
                k, v = f.group(1, 2)
                device_status[k] = v
        self._device_status = device_status

    def handle_socket_response(self, sslSocket):
        reply = self.read_line_from_socket(sslSocket)
        while reply:
            if reply.find('Update Type="InvalidateAccount"') != -1:
                self.handle_response_invalidate_account(sslSocket, reply)
            elif reply.find('Response Type="AuthToken" Status="Okay"') != -1:
                self.handle_response_auth_success(sslSocket, reply)
            elif reply.find('Update Type="Status"') != -1:
                self.handle_response_status_update(sslSocket, reply)
            elif reply.find('Response Type="DeviceState" Status="Okay"') != -1:
                self.handle_response_device_state(sslSocket, reply)
            elif reply.find('Response Type="DeviceControl" Status="Okay"') != -1:
                pass # do we need to handle this?
            reply = self.read_line_from_socket(sslSocket)

    def send_socket_command(self, command, retries = 1):
        sslSocket = None
        command_sent = False
        try:
            self.logger.info("Getting socket connection")
            sslSocket = self.socket
            if sslSocket and command:
                self.logger.info("Sending command")
                sslSocket.sendall(command.encode('utf-8'))
                command_sent = True
            else:
                self.logger.info("Command empty, skipping sending")
                command_sent = sslSocket is not None
            self.logger.info("Handling socket response")
            if sslSocket:
                self.handle_socket_response(sslSocket)
            self.logger.info("Handling finished")
        except:
            self.logger.error('Sending command failed')
            if sslSocket is not None:
                sslSocket.close()
                self._cfg.socket = None
            self.logger.error(traceback.format_exc())

        if not command_sent and retries > 0:
            self.logger.info("Retrying sending command...")
            self.send_socket_command(command, retries -1)
        
    def create_connection(self):
        sslSocket = None
        cfg = self._cfg
        self.logger.info("Creating ssl context")
        sslContext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        self.logger.info("Setting up ciphers")
        sslContext.set_ciphers("HIGH:!DH:!aNULL")
        self.logger.info("Setting up verify mode")
        sslContext.verify_mode = ssl.CERT_REQUIRED if cfg.cert is not None else ssl.CERT_NONE
        if cfg.cert is not None:
            self.logger.info("Setting up verify location: {}".format(cfg.cert))
            sslContext.load_verify_locations(cafile = cfg.cert)
            self.logger.info("Setting up load cert chain: {}".format(cfg.cert))
            sslContext.load_cert_chain(cfg.cert)
        else:
            self.logger.info("Cert is empty, skipping verification")
        self.logger.info("Wrapping socket")
        sslSocket = sslContext.wrap_socket(socket(AF_INET, SOCK_STREAM), server_hostname = cfg.host)
        self.logger.info("Socket wrapped: {}".format(True if sslSocket is not None else False))

        if sslSocket is not None:
            self.logger.info("Connecting with {}:{}".format(cfg.host, cfg.port))
            sslSocket.connect((cfg.host, cfg.port))
            #sslSocket.setblocking(0)
            self.handle_socket_response(sslSocket)
        else:
            self.logger.info("Wrapping socket failed")

    @property
    def socket(self):
        sslSocket = self._cfg.socket
        if sslSocket is None:
            self.logger.info("Connection invalid, creating!")
            self.create_connection()
            sslSocket = self._cfg.socket
            if sslSocket is None:
                self.logger.error("Creating socket failed!")
        return sslSocket

    def execute(self, template, v, device_state):
        params = self._params
        params.update({ 'value' : v })
        params.update({ 'device_state' : device_state })
        self.logger.info("Executing params: {}".format(params))
        message = v
        if template is not None:
            message = template.render(**params) + '\n'
        elif CONFIG_DEVICE_CONNECTION_TEMPLATE in params:
            message = params[CONFIG_DEVICE_CONNECTION_TEMPLATE]

        self.logger.info("Checking power on template: {}".format(self._power_template))
        if self._power_template:
            self.logger.info("Power on template found, rendering")
            power_message = self._power_template.render(**params)
            self.logger.info("Power on message: {}".format(power_message))
            if power_message and power_message != '':
                self.logger.info("Executing power command")
                self.send_socket_command(power_message, 1)

        self.logger.info("Executing command: {}".format(message))
        self.send_socket_command(message, 1)
        #self.handle_response_device_state(None, xml_test)
        return self._device_status
